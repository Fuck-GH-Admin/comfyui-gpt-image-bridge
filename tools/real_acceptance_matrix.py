"""Real ComfyUI acceptance cases. Each case queues once; there is no requeue logic."""
import argparse,hashlib,json,time,io
from pathlib import Path
import requests,yaml
from PIL import Image,ImageDraw

PROJECT=Path(__file__).resolve().parents[1]
ROOT=PROJECT/'artifacts/acceptance'
COMFY_ROOT=Path('.')
BASE='http://127.0.0.1:8188'
PROXY='http://127.0.0.1:8317/v1'
FLARE='gpt-image-2.6-flare';SUNBURST='gpt-image-2.6-sunburst'
CASES={
 'flare_default':{},
 'postfix_moderation_low':{'moderation':'low','quality':'low'},
 'sunburst_default':{'model':SUNBURST},
 'reference_images_default':{'refs':2},
 'edit_mask':{'model':SUNBURST,'edit':True,'mask':True,'complexity':'high'},
 'custom_jpeg_xhigh':{'size':'Custom','custom_width':1024,'custom_height':768,'format':'jpeg','quality':'xhigh','complexity':'low'},
 'custom_webp_max':{'model':SUNBURST,'size':'Custom','custom_width':1024,'custom_height':1024,'format':'webp','quality':'max','complexity':'medium','moderation':'low'},
 'transparent_png':{'background':'transparent','quality':'low','prompt':'A single simple orange circle icon. Completely transparent background, no shadow or surrounding objects.'},
 'batch_2k':{'size':'2048x1152','n':2,'quality':'low','complexity':'low'},
 'preset_4k':{'model':SUNBURST,'size':'3840x2160','quality':'low','complexity':'low'},
 'generate_16_references':{'refs':16,'quality':'low'},
 'edit_15_references':{'edit':True,'refs':15,'quality':'low'},
 'reference_responses':{'refs':1,'reference_mode':'responses','responses_model':'gpt-6.1-sol','quality':'low'},
 'generic_images':{'generic':True,'protocol':'images','quality':'low'},
 'generic_chat':{'generic':True,'protocol':'chat_completions','quality':'low'},
 'generic_async_fallback':{'generic':True,'protocol':'images','async':True,'quality':'low'},
}

def fixtures():
 folder=COMFY_ROOT/'input/bridge-main-acceptance';folder.mkdir(exist_ok=True)
 base=Image.new('RGB',(512,512),'#204a78');d=ImageDraw.Draw(base);d.ellipse((50,150,210,310),fill='orange');d.rectangle((300,150,460,310),fill='yellow');base.save(folder/'base.png')
 mask=Image.new('L',(512,512),0);ImageDraw.Draw(mask).rectangle((280,130,480,330),fill=255);mask.save(folder/'mask.png')
 for i in range(1,17):
  im=Image.new('RGB',(128+i*4,128+i*2),(i*13%255,i*53%255,i*97%255));ImageDraw.Draw(im).ellipse((20,20,80,80),fill='white');im.save(folder/f'ref-{i}.png')

def run(name,options,key):
 def call(path,payload=None):
  r=requests.get(BASE+path,timeout=20) if payload is None else requests.post(BASE+path,json=payload,timeout=20)
  r.raise_for_status();return r.json()
 keyhandle=call('/gpt-image-bridge/session-credential',{'api_key':key})['credential_handle']
 if options.get('generic'):
  provider={'class_type':'GPTImageBridgeAPIProvider','inputs':{'api_key':keyhandle,'base_url':PROXY,'model':options.get('model',FLARE),'api_protocol':options.get('protocol','images'),'use_async':options.get('async',False),'use_custom_endpoints':False}}
 else:
  provider={'class_type':'GPTImageBridgeCLIProxyAPIProvider','inputs':{'api_key':keyhandle,'base_url':PROXY,'image_model':options.get('model',FLARE),'responses_model':options.get('responses_model',''),'reference_mode':options.get('reference_mode','images_edit'),'image_complexity':options.get('complexity','auto')}}
 graph={'1':provider}
 params={'provider':['1',0],'prompt':options.get('prompt','Make a simple flat graphic: an orange circle on the left and a yellow square on the right, on a matte blue background. No text.'),'size':options.get('size','auto'),'quality':options.get('quality','auto'),'background':options.get('background','opaque'),'output_format':options.get('format','png'),'moderation':options.get('moderation','auto'),'n':options.get('n',1),'timeout_sec':300}
 for k in ('custom_width','custom_height'):
  if k in options:params[k]=options[k]
 if options.get('edit'):
  graph['10']={'class_type':'LoadImage','inputs':{'image':'bridge-main-acceptance/base.png'}}
  params['base_image（Image 1）']=['10',0];params['prompt']='Change only the yellow square on the right into a green triangle. Preserve the blue background and orange circle on the left.'
 if options.get('mask'):
  graph['11']={'class_type':'LoadImageMask','inputs':{'image':'bridge-main-acceptance/mask.png','channel':'red'}};params['mask']=['11',0]
 refs={}
 for i in range(1,options.get('refs',0)+1):
  nid=str(20+i);graph[nid]={'class_type':'LoadImage','inputs':{'image':f'bridge-main-acceptance/ref-{i}.png'}}
  refs[f'image_{i+1}']=[nid,0]
  if not options.get('edit'):params[f'reference_{i}']=[nid,0]
 if options.get('edit') and refs:
  graph['12']={'class_type':'GPTImageBridgeReferenceList','inputs':refs};params['references（Image 2 开始）']=['12',0]
 graph['2']={'class_type':'GPTImageBridgeEdit' if options.get('edit') else 'GPTImageBridgeGenerate','inputs':params}
 graph['3']={'class_type':'SaveImage','inputs':{'images':['2',0],'filename_prefix':'Bridge-Main-Acceptance/'+name}}
 graph['4']={'class_type':'PreviewAny','inputs':{'source':['2',2]}}
 start=time.monotonic();queued=call('/prompt',{'prompt':graph});pid=queued['prompt_id'];print('QUEUED',name,pid,flush=True)
 record={'case':name,'options':options,'prompt_id':pid,'queue_status':'pending'}
 previous=0
 while time.monotonic()-start<330:
  h=call('/history/'+pid)
  if pid in h:break
  elapsed=int(time.monotonic()-start)
  if elapsed>=previous+30:print('WAIT',name,elapsed,flush=True);previous=elapsed
  time.sleep(1)
 else:
  record['queue_status']='unknown_timeout';(ROOT/(name+'.json')).write_text(json.dumps(record,indent=2));raise RuntimeError('Task state unknown; stop and inspect before more requests')
 item=h[pid];assert key not in json.dumps(item),'Key leaked to history'
 record.update(queue_status=item['status']['status_str'],elapsed_seconds=round(time.monotonic()-start,2),history_key_absent=True)
 if record['queue_status']=='success':
  report=item.get('outputs',{}).get('4',{}).get('text',[]);record['request_report']=json.loads(report[0]) if report else None
  record['images']=[]
  for e in item['outputs']['3']['images']:
   p=COMFY_ROOT/'output'/e.get('subfolder','')/e['filename'];data=p.read_bytes()
   with Image.open(io.BytesIO(data)) as im:
    assert key not in json.dumps(im.info),'Key leaked to PNG metadata'
    record['images'].append({'filename':p.name,'format':im.format,'mode':im.mode,'dimensions':list(im.size),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'alpha_extrema':list(im.getchannel('A').getextrema()) if 'A' in im.getbands() else None})
   (ROOT/p.name).write_bytes(data)
  record['checks']={'count_matches_n':len(record['images'])==params['n'],'output_decodes':True,'key_absent':True}
  if params['background']=='transparent':record['checks']['alpha_preserved']=all(i['alpha_extrema'] is not None and i['alpha_extrema'][0]<255 for i in record['images'])
 else:
  errors=[d.get('exception_message','') for ev,d in item['status'].get('messages',[]) if ev=='execution_error'];record['errors']=[]
  for error in errors:
   try:record['errors'].append(json.loads(error))
   except ValueError:record['errors'].append(error[:1200])
 assert key not in json.dumps(record)
 (ROOT/(name+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
 print('RESULT',name,record['queue_status'],record.get('checks',record.get('errors')),flush=True)
 return record

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--case',action='append',choices=list(CASES),required=True);p.add_argument('--proxy-config',type=Path,required=True);p.add_argument('--comfy-root',type=Path,required=True);p.add_argument('--output-dir',type=Path,default=ROOT);p.add_argument('--comfy-url',default=BASE);p.add_argument('--proxy-url',default=PROXY);args=p.parse_args()
 ROOT=args.output_dir.resolve();ROOT.mkdir(parents=True,exist_ok=True);COMFY_ROOT=args.comfy_root.resolve();BASE=args.comfy_url.rstrip('/');PROXY=args.proxy_url.rstrip('/')
 if not (COMFY_ROOT/'main.py').is_file():p.error('--comfy-root must point to the actual ComfyUI directory')
 key=yaml.safe_load(args.proxy_config.expanduser().read_text())['access']['api-keys'][0];fixtures()
 for name in args.case:run(name,CASES[name],key)
