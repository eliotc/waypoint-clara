"""Launch the real Clara app on loopback, using a verified read-only evaluation DB."""
import argparse
import hashlib
import os
from pathlib import Path
import secrets
import sys

from evaluation.local_database import ROOT, connect_verified, snapshot, state_file, database_uri


def source_hashes():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT/'backend').glob('*.py'))}


def build_app(state, model):
    connect_verified(state).close()
    os.environ['DATABASE_URL'] = database_uri(state['readonly_dsn'])
    os.environ['MODEL_NAME'] = model
    os.environ['WAYPOINT_EVAL_EMBEDDINGS_READY'] = '1' if state['embeddings_ready'] else '0'
    sys.path.insert(0, str(ROOT / 'backend'))
    import main as clara_main
    from agent import INSTRUCTION
    from fastapi import Request
    # Local import annotation must be resolvable by FastAPI.
    globals()['Request'] = Request
    app = clara_main.app
    hashes = source_hashes()

    @app.middleware('http')
    async def authenticate(request, call_next):
        if not secrets.compare_digest(request.headers.get('x-waypoint-evaluation', ''), state['http_token']):
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail':'Evaluation token required'}, status_code=403)
        return await call_next(request)

    # Wrap ASGI so WebSockets also require the private token, before app/model setup.
    @app.get('/evaluation/metadata')
    async def metadata(request: Request):
        import asyncio
        database = await asyncio.to_thread(snapshot, state)
        return {'protocol_version': 1, 'mode':'readonly_evaluation', 'model': model,
                'dataset_id':state['dataset_id'], 'database':state['database'],
                'clock_anchor':state['clock_anchor'], 'embeddings_ready':state['embeddings_ready'],
                'instruction_sha256':hashlib.sha256(INSTRUCTION.encode()).hexdigest(),
                'source_hashes':hashes, 'snapshot':database}

    class AuthenticatedApp:
        async def __call__(self, scope, receive, send):
            if scope['type'] == 'websocket':
                headers = dict(scope.get('headers', []))
                supplied = headers.get(b'x-waypoint-evaluation', b'').decode()
                if not secrets.compare_digest(supplied, state['http_token']):
                    await send({'type':'websocket.close','code':1008})
                    return
            await app(scope, receive, send)
    return AuthenticatedApp()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--model', default='gemini-3.1-flash-live-preview')
    args = parser.parse_args()
    state = state_file(args.state)
    if state['status'] != 'ready':
        parser.error('Database state is not ready')
    import uvicorn
    uvicorn.run(build_app(state, args.model), host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
