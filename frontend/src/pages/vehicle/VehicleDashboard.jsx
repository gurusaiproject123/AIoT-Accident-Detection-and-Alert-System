import {useCallback,useEffect,useState} from "react";
import {useAuth} from "../auth/useAuth";
import "./vehicle.css";
import { API_BASE_URL as BASE } from '../../config/api';
const show=value=>Number.isFinite(Number(value))&&value!=null?Number(value).toFixed(3):"—";
export default function VehicleDashboard(){
  const {session,profile,signOut}=useAuth();const token=session?.access_token;
  const [cars,setCars]=useState([]),[selected,setSelected]=useState(""),[state,setState]=useState(null),[motion,setMotion]=useState(null),[error,setError]=useState("");
  const [refresh,setRefresh]=useState(0),[loading,setLoading]=useState(true);
  const request=useCallback(async(path,signal)=>{
    const r=await fetch(BASE+path,{signal,cache:"no-store",headers:{Authorization:`Bearer ${token}`}});
    const body=await r.json().catch(()=>null);
    if(!r.ok)throw Error(typeof body?.detail==="string"?body.detail:`Request failed (${r.status}).`);
    return body;
  },[token]);
  useEffect(()=>{
    const controller=new AbortController();let active=true;
    async function load(){try{const all=[];for(let offset=0;;){const page=await request(`/api/vehicles?limit=100&offset=${offset}`,AbortSignal.any([controller.signal,AbortSignal.timeout(12000)]));
      if(!Array.isArray(page?.items))throw Error("Invalid vehicle list.");all.push(...page.items);offset+=page.items.length;if(!page.items.length||offset>=page.total)break;}
      if(active){setCars(all);setSelected(old=>all.some(c=>c.id===old)?old:(all[0]?.id??""));setError("");}}
      catch(e){if(active)setError(e.message);}finally{if(active)setLoading(false);}}
    void load();return()=>{active=false;controller.abort();};
  },[request,refresh]);
  useEffect(()=>{
    if(!selected)return;const controller=new AbortController();let active=true,timer;
    async function poll(){try{const signal=AbortSignal.any([controller.signal,AbortSignal.timeout(12000)]);
      const [status,sample]=await Promise.all([request(`/api/vehicles/${selected}/status`,signal),request(`/api/vehicles/${selected}/motion/latest`,signal)]);
      if(active){setState(status);setMotion(sample);setError("");}}
      catch(e){if(active)setError(e.message);}finally{if(active)timer=setTimeout(poll,4000);}}
    void poll();return()=>{active=false;controller.abort();clearTimeout(timer);};
  },[selected,request,refresh]);
  const current=state?.vehicle_id===selected?state:null;
  const sample=motion?.vehicle_id===selected?motion.sample:null;
  const gps=current?.gps;
  return <main className="vehicle-root"><header><div><p>AIoT RESPONSE · OWNER</p><h1>My car monitoring</h1><span>{profile?.name??profile?.full_name}</span></div><button onClick={()=>signOut().catch(e=>setError(e.message))}>Sign out</button></header>
    {error&&<p role="alert" className="vehicle-error">{error} Previously loaded readings may be stale.</p>}
    <section className="vehicle-card"><h2>Local driving</h2><p>Connect your phone to <strong>AI_GURUS_CAR</strong> using the car Wi-Fi password, then open <strong>http://192.168.4.1</strong> and tap <strong>Acquire local control</strong>. The updated firmware does not require a separate driving-page login.</p>
      <p>This dashboard monitors the car. It does not acquire a backend controller session or send movement commands.</p><small>The car Wi-Fi does not provide internet access. You may need to switch back to your normal Wi-Fi/mobile connection to view this dashboard. Monitoring and hospital alerts require the ESP32-to-backend connection.</small></section>
    <section className="vehicle-card"><label>Registered car<select value={selected} onChange={e=>setSelected(e.target.value)}>{!cars.length&&<option value="">No registered cars</option>}{cars.map(car=><option key={car.id} value={car.id}>{car.registration} · {car.model??"Car"}</option>)}</select></label>
      <button onClick={()=>{setLoading(true);setRefresh(v=>v+1);}} disabled={loading}>{loading?"Loading…":"Refresh monitoring"}</button>
      {!loading&&!cars.length&&<p>Ask the administrator to link a registered car to your owner account.</p>}</section>
    <section className="vehicle-card"><h2>Backend connection and location</h2><p>Device: {current?.device?.device_code??"Not loaded / unassigned"}</p><p>Connection: {current?.connection_status??"Checking…"}</p>
      <p>Last heartbeat: {current?.device?.last_seen_at?new Date(current.device.last_seen_at).toLocaleString():"Never / unavailable"}</p>
      {gps?.latitude!=null&&gps?.longitude!=null?<p><a href={`https://www.google.com/maps?q=${gps.latitude},${gps.longitude}`} target="_blank" rel="noreferrer">Last known location: {gps.latitude}, {gps.longitude}</a> · {gps.status} · {gps.recorded_at?new Date(gps.recorded_at).toLocaleString():"Time unavailable"}</p>:<p>GPS location unavailable</p>}</section>
    <section className="vehicle-card"><h2>Latest uploaded MPU6050 sample</h2>{sample?<><p>Recorded: {new Date(sample.recorded_at).toLocaleString()}</p><p>Acceleration (m/s²): X {show(sample.accel_x)} · Y {show(sample.accel_y)} · Z {show(sample.accel_z)}</p><p>Rotation (deg/s): X {show(sample.gyro_x)} · Y {show(sample.gyro_y)} · Z {show(sample.gyro_z)}</p></>:<p>No uploaded motion sample available.</p>}<small>These are the latest stored readings, not a live motor feedback signal. Full recordings are uploaded in 1,600-sample windows for the existing model.</small></section>
  </main>;
}
