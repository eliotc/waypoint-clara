"""Browser-controller logic tested in Node with fake DOM/audio/socket, no browser."""
from pathlib import Path
import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which('node'), 'Node required for browser-controller logic checks')
class ShowcasePlaybackTests(unittest.TestCase):
    def test_ack_waits_for_audio_end_and_stop_detaches_socket(self):
        script = r'''
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
class Element {
 constructor(){this.style={};this.handlers={};this.children=[];this.textContent='';
  const classes=new Set();
  this.classList={add:(...c)=>c.forEach(x=>classes.add(x)),remove:(...c)=>c.forEach(x=>classes.delete(x)),
   contains:c=>classes.has(c),toggle:(c,force)=>{const on=force===undefined?!classes.has(c):force;if(on)classes.add(c);else classes.delete(c);return on;}};}
 addEventListener(type,fn){this.handlers[type]=fn;}
 append(...children){this.children.push(...children);}
 replaceChildren(){this.children=[];}
 setAttribute(){}
 removeAttribute(){}
 querySelector(){return new Element();}
}
const elements=new Map();const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
const sources=[],sockets=[];
class Audio {
 constructor(){this.state='running';this.currentTime=0;this.destination={};}
 async resume(){}
 async close(){this.state='closed';}
 createBuffer(channels,n,rate){return {duration:n/rate,getChannelData:()=>new Float32Array(n)};}
 createBufferSource(){const s={connect(){},start(){},stop(){}};sources.push(s);return s;}
}
class Socket {
 static OPEN=1;
 constructor(){this.readyState=1;this.sent=[];sockets.push(this);}
 send(text){this.sent.push(JSON.parse(text));}
 close(){this.closed=true;}
}
const context={document:{getElementById:get,createElement:()=>new Element()},window:{AudioContext:Audio,addEventListener(){}},location:{protocol:'http:',host:'localhost'},WebSocket:Socket,
 fetch:async()=>({ok:true,json:async()=>({id:'returning-to-study',title:'Study',subtitle:'Student',student_messages:['one','two','three','four','five','six'],turn_labels:['A goal'],criteria:[]})}),
 atob:s=>Buffer.from(s,'base64').toString('binary'),Uint8Array,DataView,Map,Set,console};
vm.runInNewContext(fs.readFileSync('frontend/assets/showcase/showcase.js','utf8'),context);
(async()=>{
 await new Promise(resolve=>setImmediate(resolve));
 await get('btnStartLive').handlers.click();
 const socket=sockets[0];socket.onopen();
 assert.equal(socket.sent[0].action,'start');
 let seq=0;const emit=body=>socket.onmessage({data:JSON.stringify({run_id:'run',seq:++seq,...body})});
 emit({type:'status',state:'connecting'});
 emit({type:'turn_start',turn_id:1,text:'Student'});
 assert.match(get('statusPill').textContent,/Question 1 of 6/);
 emit({type:'audio',turn_id:1,data:'AAA='});
 emit({type:'agent_turn_complete',turn_id:1});
 assert.equal(socket.sent.length,1,'must not ACK scheduled audio early');
 sources[0].onended();
 assert.equal(socket.sent[1].action,'playback_ack');
 assert.equal(socket.sent[1].turn_id,1);
 get('btnStopLive').handlers.click();
 assert.equal(socket.closed,true);
 assert.equal(socket.onmessage,null);
 await get('btnStartLive').handlers.click();
 const next=sockets[1];next.onopen();
 next.onmessage({data:JSON.stringify({type:'turn_start',run_id:'next',seq:1,turn_id:1,text:'Student'})});
 next.onmessage({data:JSON.stringify({type:'agent_turn_complete',run_id:'next',seq:2,turn_id:1})});
 assert.equal(next.closed,true,'missing audio must stop, not ACK');
 assert.equal(next.sent.length,1);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        root=Path(__file__).resolve().parents[2]
        result=subprocess.run(['node','-e',script],cwd=root,text=True,capture_output=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
