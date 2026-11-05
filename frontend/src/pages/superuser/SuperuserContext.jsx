import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../auth/useAuth";
import { SuperuserContext } from "./useSuperuser";
import * as api from "./api";

const empty = {incidents: [], devices: [], hospitals: [], users: [], owners: [], audit: []};
const incidentView = (r, timeline = []) => ({
  id:r.id, code:r.code, deviceId:r.device_id, detectedAt:r.detected_at,
  status:r.status, modelScore:r.model_score, impact:r.impact_summary,
  location:{label:r.location_label ?? r.location_status_label, lat:r.latitude, lng:r.longitude},
  cancellation:{windowSeconds:r.cancellation_window_seconds, deadline:r.cancellation_deadline,
    outcome:r.cancellation_outcome, by:r.cancelled_by_label, at:r.cancellation_resolved_at},
  notifications:(r.notifications ?? []).map(n=>({hospitalId:n.hospital_id, hospitalName:n.hospital_name,
    status:n.status, notifiedAt:n.notified_at, acknowledgedAt:n.acknowledged_at,
    respondedAt:n.responded_at, reason:n.decline_reason})),
  notes:(r.notes ?? []).map(n=>({at:n.created_at, text:n.body, actor:n.author_label})),
  timeline:timeline.map(e=>({at:e.created_at, type:e.event_type, text:e.message, actor:e.actor_label})),
});

export default function SuperuserProvider({ children }) {
  const {session, profile, signOut} = useAuth();
  const token = session?.access_token;
  const [data, setData] = useState(empty);
  const [overview, setOverview] = useState({});
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(Date.now);
  const [preferences, setPreferences] = useState({animations:true});
  const [toasts, setToasts] = useState([]);
  const sequence = useRef(0);
  const writing = useRef(false);
  const [revision, setRevision] = useState(0);
  const dismissToast = (id) => setToasts(list=>list.filter(t=>t.id!==id));
  const notify = (message,tone="green") => setToasts(list=>[...list.slice(-3),{id:crypto.randomUUID(),message,tone}]);

  const refresh = useCallback(async (signal) => {
    const request = ++sequence.current;
    const timeout = AbortSignal.timeout(20000);
    signal = signal ? AbortSignal.any([signal, timeout]) : timeout;
    const jobs = {
      overview:api.adminRequest("/api/admin/overview",token,{signal}),
      incidents:api.getAll("/api/admin/incidents",token,signal),
      devices:api.getAll("/api/admin/devices",token,signal),
      hospitals:api.getAll("/api/admin/hospitals",token,signal),
      users:api.getAll("/api/admin/users",token,signal),
      owners:api.getAll("/api/admin/owners",token,signal),
      vehicles:api.getAll("/api/admin/vehicles",token,signal),
      audit:api.getAll("/api/admin/audit",token,signal),
    };
    const entries = Object.entries(jobs);
    const settled = await Promise.allSettled(entries.map(([,job])=>job));
    if (request !== sequence.current) return;
    const rows = {};
    const issues = {};
    settled.forEach((item,i)=>{
      const key = entries[i][0];
      if(item.status==="fulfilled") rows[key]=item.value;
      else issues[key]=item.reason?.message ?? "Request failed.";
    });
    if (rows.overview) setOverview(rows.overview);
    setData(previous=>{
      const next = {...previous};
      if(rows.incidents) next.incidents=rows.incidents.map(r=>incidentView(r));
      if(rows.devices) next.devices=rows.devices.map(r=>({id:r.id,code:r.device_code,status:r.status,
        firmware:r.firmware_version,gps:r.gps_status,lastSeen:r.last_seen_at,lat:r.last_latitude,lng:r.last_longitude,
        vehicle:rows.vehicles?.find(v=>v.id===r.vehicle_id)?.registration ?? (r.vehicle_id ? "Linked vehicle" : "Unassigned"),
        vehicleModel:rows.vehicles?.find(v=>v.id===r.vehicle_id)?.model}));
      if(rows.hospitals) next.hospitals=rows.hospitals.map(r=>({id:r.id,code:r.code,name:r.name,city:r.city,active:r.is_active,
        phone:r.phone??"",email:r.email??"",address:r.address??"",lat:r.latitude,lng:r.longitude,registeredAt:r.created_at}));
      if(rows.owners && rows.vehicles) next.owners=rows.owners.map(r=>{
        const cars=rows.vehicles.filter(v=>v.owner_id===r.id);
        return {id:r.id,name:r.full_name,userId:r.user_id,vehicleIds:cars.map(v=>v.id),registrations:cars.map(v=>v.registration)};
      });
      if(rows.users) next.users=rows.users.map(r=>({id:r.id,name:r.full_name,email:r.email??"",role:r.role,status:r.status,
        hospitalId:r.hospital_id,ownerId:next.owners.find(o=>o.userId===r.id)?.id,lastSignIn:r.last_sign_in_at}));
      if(rows.audit) next.audit=rows.audit.map(r=>({id:r.code??r.id,at:r.created_at,actor:r.actor_label,role:r.actor_role,
        category:r.category,action:r.action,target:r.target_label??r.target_id,detail:r.detail}));
      return next;
    });
    setErrors(issues);
    setLoading(false);
  },[token]);

  useEffect(()=>{
    const controller=new AbortController();
    void refresh(controller.signal);
    const clock=setInterval(()=>setNow(Date.now()),1000);
    return ()=>{controller.abort(); ++sequence.current; clearInterval(clock);};
  },[refresh]);

  const getDetail = useCallback(async (id,signal)=>{
    const [record,timeline]=await Promise.all([
      api.adminRequest(`/api/admin/incidents/${encodeURIComponent(id)}`,token,{signal}),
      api.adminRequest(`/api/incidents/${encodeURIComponent(id)}/timeline`,token,{signal}),
    ]);
    return incidentView(record,timeline.items);
  },[token]);

  const write = async (action,message) => {
    if (writing.current) return {ok:false,error:"Another change is being saved."};
    writing.current = true;
    try {
      await action();
      notify(message);
      setRevision(v=>v+1);
      await refresh();
      return {ok:true};
    } catch(error) {
      notify(error.message,"red");
      return {ok:false,error:error.message};
    } finally { writing.current = false; }
  };
  const saveHospital = (h) => {
    const body={name:h.name,city:h.city,is_active:h.active};
    if(h.phone) body.phone=h.phone;
    if(h.email) body.email=h.email;
    if(h.address || !h.id) body.address=h.address || null;
    if(h.lat!=null) body.latitude=h.lat;
    if(h.lng!=null) body.longitude=h.lng;
    if((h.lat==null)!==(h.lng==null)) return Promise.resolve({ok:false,error:"Enter both coordinates or leave both blank."});
    return write(()=>h.id?api.updateHospital(token,h.id,body):api.createHospital(token,body),"Hospital saved.");
  };
  const toggleHospital = (id) => write(()=>api.updateHospital(token,id,{is_active:!data.hospitals.find(h=>h.id===id).active}),"Hospital status updated.");
  const saveUser = (u) => write(()=>u.id
    ? api.updateUser(token,u.id,{hospital_id:u.hospitalId})
    : api.createUser(token,u),"Account saved.");
  const toggleUser = (id) => write(()=>api.adminRequest(`/api/admin/users/${encodeURIComponent(id)}/status`,token,{
    method:"PATCH",body:JSON.stringify({status:data.users.find(u=>u.id===id).status==="active"?"suspended":"active"})}),"Account status updated.");
  const stats = {
    totalIncidents:overview.total_incidents ?? data.incidents.length,
    openIncidents:overview.open_incidents ?? data.incidents.filter(i=>!["closed","cancelled"].includes(i.status)).length,
    pendingAlerts:overview.pending_alerts ?? overview.pending_notifications ?? "—",
    onlineDevices:overview.online_devices ?? data.devices.filter(d=>d.status==="online").length,
    totalDevices:overview.total_devices ?? data.devices.length,
    activeHospitals:overview.active_hospitals ?? data.hospitals.filter(h=>h.active).length,
    totalHospitals:overview.total_hospitals ?? data.hospitals.length,
  };
  return <SuperuserContext.Provider value={{
    ...data,now,stats,loading,errors,refresh:()=>refresh(),getDetail,revision,
    profile, signOut:()=>signOut().catch(e=>notify(e.message,"red")),
    hospitalById:Object.fromEntries(data.hospitals.map(h=>[h.id,h])),
    deviceById:Object.fromEntries(data.devices.map(d=>[d.id,d])),
    toasts,dismissToast,notify,preferences,setPreference:(key,value)=>setPreferences(p=>({...p,[key]:value})),
    saveHospital,toggleHospital,saveUser,toggleUser,
    notifyHospital:(id,hospital)=>write(()=>api.routeIncident(token,id,hospital),"Hospital notified."),
    closeIncident:(id,note)=>write(()=>api.closeIncident(token,id,note),"Incident closed."),
    addIncidentNote:(id,body)=>write(()=>api.adminRequest(`/api/incidents/${encodeURIComponent(id)}/notes`,token,{method:"POST",body:JSON.stringify({body})}),"Note saved."),
  }}>{children}</SuperuserContext.Provider>;
}
