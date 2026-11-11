import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/useAuth";
import { DriveClient } from "./driveClient";
import "./vehicle.css";
const BASE=(import.meta.env.VITE_API_BASE_URL??"http://127.0.0.1:8000").replace(/\/$/,"");

export default function VehicleDashboard() {
  const {session,profile,signOut}=useAuth();
  const token=session?.access_token;
  const [cars,setCars]=useState([]),[selected,setSelected]=useState(""),[details,setDetails]=useState(null),[status,setStatus]=useState(null);
  const [error,setError]=useState(""),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[speed,setSpeed]=useState(80);
  const [control,setControl]=useState({lease:null,ack:null});
  const clientRef=useRef(null),mounted=useRef(false),pointer=useRef(null);
  const request=useCallback(async(path,options={})=>{
    const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),options.timeout??10000);
    try {
      const response=await fetch(BASE+path,{method:options.method??"GET",signal:controller.signal,cache:"no-store",
        headers:{Authorization:`Bearer ${token}`,"Content-Type":"application/json"},
        body:options.body?JSON.stringify(options.body):undefined});
      const value=await response.json().catch(()=>null);
      if(!response.ok)throw new Error(typeof value?.detail==="string"?value.detail:`Request failed (${response.status}).`);
      return value;
    }catch(e){if(e.name==="AbortError")throw new Error("Connection timed out; controller stopped. Check the backend and Wi-Fi.",{cause:e});throw e;}
    finally{clearTimeout(timer);}
  },[token]);

  useEffect(()=>{
    mounted.current=true;
    const client=new DriveClient(request,next=>{if(mounted.current)setControl(previous=>({...previous,...next}));});
    clientRef.current=client;
    const halt=()=>{pointer.current=null;void client.stop().catch(()=>{});};
    const hidden=()=>{if(document.hidden)halt();};
    const keyboard=e=>{if(e.code==="Space"&&!/INPUT|SELECT|TEXTAREA|BUTTON/.test(e.target.tagName)){e.preventDefault();halt();}};
    window.addEventListener("blur",halt);window.addEventListener("pagehide",halt);window.addEventListener("offline",halt);
    document.addEventListener("visibilitychange",hidden);document.addEventListener("keydown",keyboard);
    return()=>{mounted.current=false;void client.stop().catch(()=>{});window.removeEventListener("blur",halt);window.removeEventListener("pagehide",halt);
      window.removeEventListener("offline",halt);document.removeEventListener("visibilitychange",hidden);document.removeEventListener("keydown",keyboard);};
  },[request]);

  const loadCars=useCallback(async()=>{
    setLoading(true);setError("");
    try {
      const rows=[];
      for(let offset=0;;){const page=await request(`/api/vehicles?limit=100&offset=${offset}`);if(!Array.isArray(page.items))throw new Error("Invalid vehicle list.");
        rows.push(...page.items);offset+=page.items.length;if(!page.items.length||offset>=page.total)break;}
      if(mounted.current){setCars(rows);setSelected(old=>rows.some(c=>c.id===old)?old:(rows[0]?.id??""));}
    }catch(e){if(mounted.current)setError(e.message);}finally{if(mounted.current)setLoading(false);}
  },[request]);
  useEffect(()=>{const timer=setTimeout(()=>void loadCars(),0);return()=>clearTimeout(timer);},[loadCars]);
  useEffect(()=>{
    if(!selected)return;
    let alive=true,timer;
    async function poll(){try{const [car,health]=await Promise.all([request(`/api/vehicles/${selected}`),request(`/api/vehicles/${selected}/status`)]);
      if(alive){setDetails(car);setStatus(health);}}
      catch(e){if(alive)setError(e.message);}finally{if(alive)timer=setTimeout(poll,3000);}}
    void poll();return()=>{alive=false;clearTimeout(timer);};
  },[selected,request]);
  async function acquire(){setBusy(true);setError("");try{await clientRef.current.acquire(selected);}catch(e){setError(e.message);}finally{if(mounted.current)setBusy(false);}}
  async function stop(){setBusy(true);setError("");pointer.current=null;try{
    await clientRef.current.stop();if(selected)await request(`/api/vehicles/${selected}/stop`,{method:"POST",timeout:2000});
  }catch(e){setError(`Stop receipt could not be confirmed: ${e.message}`);}finally{if(mounted.current)setBusy(false);}}
  function hold(e,direction){if(pointer.current!==null||!clientRef.current?.lease)return;if(e.button!==undefined&&e.button!==0)return;
    e.preventDefault();pointer.current=e.pointerId;e.currentTarget.setPointerCapture(e.pointerId);
    try{clientRef.current.hold(direction,speed);}catch(err){setError(err.message);}}
  function release(e){if(pointer.current===e.pointerId){pointer.current=null;clientRef.current?.release();}}
  const buttons=[['forward','Forward'],['left','Left'],['right','Right'],['reverse','Reverse']];
  const device=status?.device,gps=status?.gps;
  return <main className="vehicle-root">
    <header><div><p>AIoT RESPONSE · OWNER</p><h1>My cars and controls</h1><span>{profile?.name??profile?.full_name}</span></div>
      <button onClick={async()=>{try{await clientRef.current?.stop();await signOut();}catch(e){setError(e.message);}}}>Sign out</button></header>
    {error&&<p className="vehicle-error" role="alert">{error}</p>}
    {control.error&&<p className="vehicle-error" role="alert">{control.error}</p>}
    <section className="vehicle-card">
      <label>My registered car<select value={selected} disabled={Boolean(control.lease)||busy} onChange={e=>{pointer.current=null;setDetails(null);setStatus(null);setSelected(e.target.value);}}>
        {!cars.length&&<option value="">No registered cars</option>}{cars.map(c=><option key={c.id} value={c.id}>{c.registration} · {c.model??"Car"}</option>)}
      </select></label><button disabled={loading||Boolean(control.lease)} onClick={()=>void loadCars()}>{loading?"Loading…":"Refresh cars"}</button>
      {!loading&&!cars.length&&<p>Ask the administrator to register a car against your linked owner record.</p>}
      {details&&<p>{details.make} {details.model} · {details.colour} <small>{details.id}</small></p>}
    </section>
    <section className="vehicle-card"><h2>Connection and GPS</h2>
      <p>Device: {device?.device_code??"Unassigned"} · {status?.connection_status??"Checking…"}</p>
      <p>Last seen: {device?.last_seen_at?new Date(device.last_seen_at).toLocaleString():"Never"}</p>
      {gps?.latitude!=null&&gps?.longitude!=null?<p><a target="_blank" rel="noreferrer" href={`https://www.google.com/maps?q=${gps.latitude},${gps.longitude}`}>Last known location: {gps.latitude}, {gps.longitude}</a> · {gps.status} · {gps.recorded_at?new Date(gps.recorded_at).toLocaleString():"Time unknown"}</p>:<p>GPS location unavailable</p>}
    </section>
    <section className="vehicle-card"><h2>Drive your car</h2><p>Hold a direction to move. Release to stop. Begin with wheels raised.</p>
      <label>Speed: {speed}/255<input type="range" min="0" max="120" value={speed} disabled={Boolean(control.lease)} onChange={e=>setSpeed(Number(e.target.value))}/></label>
      <button disabled={!selected||busy||Boolean(control.lease)} onClick={()=>void acquire()}>{busy?"Please wait…":control.lease?"Controller acquired":"Acquire controller"}</button>
      <div className="vehicle-pad">{buttons.map(([direction,label])=><button key={direction} className={`drive-${direction}`} disabled={!control.lease||busy}
        onContextMenu={e=>e.preventDefault()} onPointerDown={e=>hold(e,direction)} onPointerUp={release} onPointerCancel={release} onLostPointerCapture={release}
        onKeyDown={e=>{if((e.key==="Enter"||e.key===" ")&&!e.repeat){e.preventDefault();try{clientRef.current.hold(direction,speed);}catch(err){setError(err.message);}}}}
        onKeyUp={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();clientRef.current.release();}}}
        onBlur={()=>clientRef.current?.release()}>{label}</button>)}</div>
      <button className="vehicle-stop" disabled={!selected||busy} onClick={()=>void stop()}>STOP / End controller</button>
      <p role="status">{control.lease?`Controller active · ${Math.ceil(control.remaining??control.lease.expires_in_seconds)} seconds remaining` : "Controller released"}</p>
      <p>Device acknowledgment: {control.ack?`#${control.ack.seq}: ${control.ack.applied?"outputs commanded":"stopped"} (${control.ack.reason})`:"None yet"}</p>
      <small>Acknowledgment reports GPIO/PWM settings, not measured wheel motion. Wi-Fi loss invokes the ESP32 command watchdog. Keep the physical power switch accessible.</small>
    </section>
  </main>;
}
