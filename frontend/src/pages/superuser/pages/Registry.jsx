import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "../../auth/useAuth";
import { adminRequest, getAll } from "../api";
import { useSuperuser } from "../useSuperuser";
import { Field, Modal, PageHeading, Panel } from "../components/ui";
import "./registry.css";

const definitions = {
  owners: {title:"Owners", singular:"owner", fields:[
    ["full_name","Full name","text",true,200], ["phone","Phone","tel",false,30], ["email","Email","email",false,254],
  ]},
  vehicles: {title:"Vehicles", singular:"vehicle", fields:[
    ["registration","Registration","text",true,30], ["owner_id","Registered owner","owner",true],
    ["make","Make","text",false,100], ["model","Model","text",false,100], ["colour","Colour","text",false,50],
  ]},
  devices: {title:"ESP32 registry", singular:"device", fields:[
    ["device_code","Device code","text",true,40], ["vehicle_id","Vehicle","vehicle",false],
    ["label","Label","text",false,200], ["firmware_version","Firmware version","text",false,100], ["is_active","Active","checkbox"],
  ]},
};

// Kept outside the page component so clock/context updates never remount the fields.
function RegistryForm({kind, record, owners, vehicles, devices, onSave, onClose}) {
  const def = definitions[kind];
  const [values,setValues] = useState(()=>Object.fromEntries(def.fields.map(([key,,type])=>[key,record?.[key] ?? (type==="checkbox" ? true : "")])));
  const [rotate,setRotate] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const busyRef = useRef(false);
  const update = (key,value)=>setValues(v=>({...v,[key]:value}));
  async function submit(event) {
    event.preventDefault();
    if(busyRef.current)return;
    busyRef.current=true; setBusy(true);setError("");
    const body={...values};
    for(const [key,,type] of def.fields) {
      if(type!=="checkbox")body[key]=String(body[key]??"").trim() || null;
    }
    if(kind==="devices") {
      if(record)delete body.device_code;
      else body.device_code=String(body.device_code??"").toUpperCase();
      if(record && rotate)body.rotate_secret=true;
    }
    try { await onSave(body,record?.id); }
    catch(e) {setError(e.message);}
    finally {busyRef.current=false;setBusy(false);}
  }
  return <Modal title={`${record?"Edit":"Register"} ${def.singular}`} onClose={()=>{if(!busy)onClose();}}>
    <form onSubmit={submit} className="registry-form">
      {def.fields.map(([key,label,type,required,max])=>{
        if(kind==="devices" && record && key==="device_code")return <p key={key}><strong>Device:</strong> {record.device_code}</p>;
        const choices=type==="owner"?owners:type==="vehicle"?vehicles:[];
        return <Field key={key} label={label}>
          {type==="owner"||type==="vehicle" ? <select required={required} disabled={busy} value={values[key]} onChange={e=>update(key,e.target.value)}>
            <option value="">{required?"Select…":"Unassigned"}</option>
            {choices.map(row=><option key={row.id} value={row.id}>
              {row.full_name??row.registration} {type==="vehicle" && devices.some(d=>d.id!==record?.id && d.vehicle_id===row.id && d.is_active)?"(another active device linked)":""}
            </option>)}
          </select> : type==="checkbox" ? <input type="checkbox" disabled={busy} checked={values[key]} onChange={e=>update(key,e.target.checked)}/> :
          <input type={type} required={required} maxLength={max} minLength={key==="full_name"||key==="registration"?2:key==="phone"?7:undefined}
            pattern={key==="device_code"?"[A-Za-z0-9-]{3,40}":undefined} disabled={busy} value={values[key]} onChange={e=>update(key,e.target.value)}/>}
        </Field>;
      })}
      {kind==="owners" && <p>Contact registration does not create a login. After adding a car, use Users and roles to create and link the owner account.</p>}
      {kind==="devices" && record && <Field label="Replace device secret"><input type="checkbox" checked={rotate} disabled={busy} onChange={e=>setRotate(e.target.checked)}/> Existing firmware credentials will stop working.</Field>}
      {kind==="devices" && <p>Stop the car and end its controller session before changing assignments, active state or credentials.</p>}
      {error && <p role="alert" className="registry-error">{error}</p>}
      <div className="registry-actions"><button type="button" className="su-btn su-btn-outline" disabled={busy} onClick={onClose}>Cancel</button>
        <button className="su-btn su-btn-primary" disabled={busy}>{busy?"Saving…":"Save"}</button></div>
    </form>
  </Modal>;
}

function ProvisioningSecret({result,onClose}) {
  const [saved,setSaved]=useState(false);
  const config=`constexpr char DEVICE_ID[] = "${result.device.id}";\nconstexpr char VEHICLE_ID[] = "${result.device.vehicle_id??"REPLACE_VEHICLE_UUID"}";\nconstexpr char DEVICE_SECRET[] = "${result.device_secret}";`;
  return <Modal title="Save the ESP32 credentials" onClose={()=>{if(saved)onClose();}}>
    <p>This secret is shown only now. Copy it into your private config.h.</p>
    <textarea aria-label="Firmware credentials" className="registry-secret" rows={6} readOnly value={config} onFocus={e=>e.target.select()}/>
    {!result.device.vehicle_id && <p>Assign a vehicle before using the firmware for driving or telemetry.</p>}
    <label><input type="checkbox" checked={saved} onChange={e=>setSaved(e.target.checked)}/> I saved the credentials securely.</label>
    <button className="su-btn su-btn-primary" disabled={!saved} onClick={onClose}>Done</button>
  </Modal>;
}

export default function Registry({kind="devices",compact=false}) {
  const {session}=useAuth();
  const {refresh:refreshDashboard}=useSuperuser();
  const token=session?.access_token;
  const [data,setData]=useState({owners:[],vehicles:[],devices:[]});
  const [loading,setLoading]=useState(true),[error,setError]=useState(""),[query,setQuery]=useState("");
  const [editing,setEditing]=useState(null),[secret,setSecret]=useState(null);
  const requestVersion=useRef(0);
  const load=useCallback(async()=>{
    const version=++requestVersion.current;setLoading(true);setError("");
    try {
      const [owners,vehicles,devices]=await Promise.all(["owners","vehicles","devices"].map(name=>getAll(`/api/admin/${name}`,token,AbortSignal.timeout(15000))));
      if(version===requestVersion.current)setData({owners,vehicles,devices});
    }catch(e){if(version===requestVersion.current)setError(e.message);}
    finally{if(version===requestVersion.current)setLoading(false);}
  },[token]);
  useEffect(()=>{const timer=setTimeout(()=>void load(),0);const versions=requestVersion;return()=>{clearTimeout(timer);++versions.current;};},[load]);
  async function save(body,id) {
    const result=await adminRequest(`/api/admin/${kind}${id?`/${id}`:""}`,token,{method:id?"PATCH":"POST",body:JSON.stringify(body),signal:AbortSignal.timeout(15000)});
    setEditing(null);
    if(kind==="devices" && result.device_secret)setSecret(result);
    void load();void refreshDashboard();
  }
  const def=definitions[kind];
  const rows=data[kind].filter(row=>JSON.stringify(row).toLowerCase().includes(query.trim().toLowerCase()));
  return <div className="registry-page">
    {!compact && <PageHeading eyebrow="Superuser / Registry" title={def.title} subtitle="Use existing owner records when registering additional cars."/>}
    <div className="registry-actions"><button className="su-btn su-btn-primary" disabled={loading} onClick={()=>setEditing({})}>Register {def.singular}</button>
      <button className="su-btn su-btn-outline" onClick={()=>void load()} disabled={loading}>Refresh registry</button>
      <input aria-label={`Search ${def.title}`} placeholder={`Search ${def.title.toLowerCase()}…`} value={query} onChange={e=>setQuery(e.target.value)}/></div>
    {loading && <p role="status">Loading registry…</p>}
    {error && <p role="alert" className="registry-error">{error} Check the list before retrying an uncertain write. A saved device with a lost secret needs credential rotation.</p>}
    <Panel title={compact?"Registration and assignment":undefined}>
      <div className="su-table-wrap"><table className="su-table"><thead><tr>
        <th>{kind==="owners"?"Owner":kind==="vehicles"?"Registration":"Device"}</th><th>Details</th><th>Assignment</th><th>Action</th>
      </tr></thead><tbody>{rows.map(row=><tr key={row.id}>
        <td><strong>{row.full_name??row.registration??row.device_code}</strong><small className="registry-id">{row.id}</small></td>
        <td>{kind==="owners"?<>{row.phone??"—"}<br/>{row.email??"—"}</>:kind==="vehicles"?`${row.make??""} ${row.model??""} · ${row.colour??""}`:`${row.label??""} · ${row.is_active?"Active":"Inactive"}`}</td>
        <td>{kind==="owners"?(row.user_id?"Login linked":"Contact only"):kind==="vehicles"?(data.owners.find(o=>o.id===row.owner_id)?.full_name??row.owner_id):(data.vehicles.find(v=>v.id===row.vehicle_id)?.registration??"Unassigned")}</td>
        <td><button className="su-btn su-btn-outline" onClick={()=>setEditing(row)}>Edit</button></td>
      </tr>)}</tbody></table></div>
      {!loading&&!rows.length&&<p>No records found.</p>}
    </Panel>
    {editing && <RegistryForm key={editing.id??"new"} kind={kind} record={editing.id?editing:null} {...data} onSave={save} onClose={()=>setEditing(null)}/>}
    {secret && <ProvisioningSecret result={secret} onClose={()=>setSecret(null)}/>}
  </div>;
}
