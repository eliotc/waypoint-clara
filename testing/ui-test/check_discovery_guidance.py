"""Isolated layout check. Requires optional playwright and installed Chromium. No model/analytics requests."""
import asyncio,json,mimetypes
from pathlib import Path
from urllib.parse import urlparse,unquote
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[2]
from datetime import datetime, timezone
from uuid import uuid4
OUT=ROOT/'evaluation/runs'/('ui-discovery-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8]);OUT.mkdir(exist_ok=False)
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True)
  context=await browser.new_context()
  async def route(r):
   u=urlparse(r.request.url)
   if u.netloc!='127.0.0.1:8866':return await r.abort()
   rel=unquote(u.path).lstrip('/') or 'index.html'
   file=(ROOT/'frontend'/rel).resolve()
   if not file.is_relative_to(ROOT/'frontend') or not file.is_file():return await r.fulfill(status=404,body='')
   await r.fulfill(body=file.read_bytes(),content_type=mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
  await context.route('**/*',route)
  await context.add_init_script("localStorage.setItem('waypointTourSeen','1'); window.WebSocket=class {static OPEN=1; readyState=0; send(){} close(){}};")
  results=[]
  for label,size in [('desktop',{'width':1280,'height':900}),('mobile',{'width':390,'height':844}),('small-mobile',{'width':360,'height':640})]:
   page=await context.new_page();await page.set_viewport_size(size)
   errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   await page.goto('http://127.0.0.1:8866/',wait_until='load')
   guidance=page.locator('.discovery-guidance');await guidance.wait_for(state='visible')
   assert await guidance.locator('strong').inner_text()=='Explore options with AI · Fictional-data demo'
   await page.screenshot(path=str(OUT/(label+'.png')))
   summary=guidance.locator('summary');await summary.focus();await page.keyboard.press('Enter')
   assert await guidance.locator('details').get_attribute('open') is not None
   await page.screenshot(path=str(OUT/(label+'-expanded.png')))
   geometry=await page.evaluate("""() => ({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,input:document.getElementById('textInput').getBoundingClientRect().toJSON(),send:document.getElementById('sendBtn').getBoundingClientRect().toJSON(),messages:document.getElementById('viaMessages').getBoundingClientRect().toJSON()})""")
   assert geometry['scrollWidth'] <= size['width']+1,geometry
   assert geometry['input']['bottom']<=size['height'],geometry
   assert geometry['send']['right']<=size['width'],geometry
   assert geometry['messages']['height']>=40,geometry
   assert not errors,errors
   results.append({'viewport':label,'geometry':geometry,'page_errors':errors,'details_keyboard_toggle':True})
   await page.close()
  (OUT/'checks.json').write_text(json.dumps(results,indent=2)+'\n')
  await browser.close()
 print(OUT)
if __name__ == '__main__':
 asyncio.run(main())
