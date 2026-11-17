import asyncio

from fastapi import HTTPException
from postgrest.exceptions import APIError

from app.localdb.storage import MySQLDatabase
from app.services.hospital_inbox import HospitalInbox
from app.schemas.alerts import AlertActionResponse,RoutingOutcomeResponse


def call(name,params):
    try:
        return MySQLDatabase().rpc(name,params).execute().data
    except APIError as exc:
        status={'42501':403,'P0002':404,'23514':409,'23505':409,'22023':422,'40001':409}.get(exc.code,503)
        raise HTTPException(status,exc.message if status!=503 else 'Local hospital operation failed.') from None


class LocalHospitalService(HospitalInbox):
    async def accept_alert(self,alert_id,caller):
        return await asyncio.to_thread(self.respond,alert_id,caller,'accept')

    async def decline_alert(self,alert_id,reason,caller):
        return await asyncio.to_thread(self.respond,alert_id,caller,'decline',reason)

    def respond(self,alert_id,caller,action,reason=None):
        self.get_authorized_alert(alert_id,caller)
        call('hospital_'+action+'_notification',{'p_actor_id':str(caller.id),'p_notification_id':str(alert_id),'p_reason':reason})
        alert=self.get_authorized_alert(alert_id,caller)
        return AlertActionResponse(alert=alert,incident_status=alert.incident.status)

    async def manual_notify_hospital(self,incident_id,hospital_id,caller):
        return await asyncio.to_thread(self.manual,incident_id,hospital_id,caller)

    def manual(self,incident_id,hospital_id,caller):
        result=call('route_incident_manually',{'p_actor_id':str(caller.id),'p_incident_id':str(incident_id),'p_hospital_id':str(hospital_id)})
        alert=self.get_authorized_alert(result['id'],caller)
        attempted=MySQLDatabase().table('incident_notifications').select('hospital_id').eq('incident_id',str(incident_id)).execute().data
        return RoutingOutcomeResponse(incident_id=incident_id,incident_code=alert.incident.code,
            incident_status=alert.incident.status,resolved=True,reason='Hospital notification recorded.',alert=alert,
            attempted_hospital_ids=[r['hospital_id'] for r in attempted])


local_hospital_service=LocalHospitalService()
