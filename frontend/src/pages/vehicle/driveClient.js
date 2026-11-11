// A controller session is intentionally kept only in memory.
export class DriveClient {
  constructor(request, changed=()=>{}) {
    this.request=request;this.changed=changed;this.lease=null;this.vehicle=null;this.sequence=0;
    this.direction=null;this.speed=80;this.generation=0;this.timer=null;this.renewTimer=null;
    this.statusTimer=null;this.inFlight=false;this.acquiring=false;this.maintenance=false;
  }
  emit(extra={}) {this.changed({lease:this.lease,...extra});}
  clearTimers(){clearTimeout(this.timer);clearInterval(this.renewTimer);clearInterval(this.statusTimer);}
  async acquire(vehicle) {
    if(this.acquiring||this.lease)throw new Error("End the existing controller first.");
    this.acquiring=true;const generation=++this.generation;
    try {
      const lease=await this.request(`/api/vehicles/${vehicle}/control-sessions`,{method:"POST"});
      if(generation!==this.generation){await this.request(`/api/control-sessions/${lease.id}/end`,{method:"POST"}).catch(()=>{});return;}
      this.lease=lease;this.vehicle=vehicle;this.sequence=0;this.emit({error:"",ack:null});
      this.renewTimer=setInterval(()=>void this.maintain(true),10000);
      this.statusTimer=setInterval(()=>void this.maintain(false),1500);
    }finally{this.acquiring=false;}
  }
  async maintain(renew) {
    if(!this.lease||this.maintenance)return;
    this.maintenance=true;const lease=this.lease;
    try{
      const status=await this.request(`/api/control-sessions/${lease.id}${renew?"/renew":""}`,{method:renew?"POST":"GET"});
      if(this.lease===lease)this.emit({ack:status.device_ack,remaining:status.expires_in_seconds});
    }catch(e){if(this.lease===lease){void this.stop().catch(()=>{});this.emit({error:e.message});}}
    finally{this.maintenance=false;}
  }
  hold(direction,speed=80) {
    if(!this.lease)throw new Error("Acquire control first.");
    if(!["forward","reverse","left","right"].includes(direction))throw new Error("Unknown direction.");
    if(!Number.isInteger(speed)||speed<0||speed>120)throw new Error("Invalid speed.");
    this.direction=direction;this.speed=speed;clearTimeout(this.timer);void this.pump();
  }
  release(){if(this.lease){this.direction="stop";clearTimeout(this.timer);void this.pump();}}
  async pump() {
    if(this.inFlight||!this.lease||!this.direction)return;
    const lease=this.lease,direction=this.direction,generation=this.generation;
    this.inFlight=true;
    try {
      await this.request(`/api/control-sessions/${lease.id}/commands`,{method:"POST",timeout:1200,
        body:{sequence_number:++this.sequence,direction,speed:direction==="stop"?0:this.speed,sent_at:new Date().toISOString()}});
      if(generation===this.generation&&this.direction===direction&&direction==="stop")this.direction=null;
    }catch(e){if(generation===this.generation){void this.stop().catch(()=>{});this.emit({error:e.message});}}
    finally {
      this.inFlight=false;
      if(this.lease&&this.direction)this.timer=setTimeout(()=>void this.pump(),this.direction==="stop"?0:70);
    }
  }
  async stop() {
    ++this.generation;this.direction=null;this.clearTimers();const lease=this.lease;
    this.lease=null;this.emit({ack:null});
    if(!lease)return;
    // Server request is best effort; the ESP32 fresh-command watchdog is independent.
    await this.request(`/api/control-sessions/${lease.id}/end`,{method:"POST",timeout:1500});
  }
}
