import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizeVerifiedProfile,homeForProfile} from '../accountRules.js';
import {fetchVerifiedProfile,signInError} from '../authService.js';
const base={id:'USER',full_name:'Demo',status:'active',hospital_id:null,owner_id:null};
test('verified roles redirect to the three separate interfaces',()=>{
 for(const [role,extra,path] of [['superuser',{},'/superuser'],['hospital_staff',{hospital_id:'H1'},'/hospital'],['car_owner',{owner_id:'O1'},'/vehicle']]){
  const p=normalizeVerifiedProfile({...base,role,...extra},'USER');assert.equal(homeForProfile(p),path);
 }
});
test('staff require a hospital; owner/admin must have none',()=>{
 assert.throws(()=>normalizeVerifiedProfile({...base,role:'hospital_staff'},'USER'));
 for(const role of ['superuser','car_owner']) assert.throws(()=>normalizeVerifiedProfile({...base,role,hospital_id:'H1',owner_id:role==='car_owner'?'O1':null},'USER'));
});
test('owner requires owner link; staff/admin reject that link',()=>{
 assert.throws(()=>normalizeVerifiedProfile({...base,role:'car_owner'},'USER'));
 assert.throws(()=>normalizeVerifiedProfile({...base,role:'superuser',owner_id:'O1'},'USER'));
});
test('suspended, unknown, mismatched and incomplete profiles fail closed',()=>{
 for(const extra of [{status:'suspended'},{role:'unassigned'},{id:'SOMEONE_ELSE'},{hospital_id:undefined}]){
  assert.throws(()=>normalizeVerifiedProfile({...base,role:'superuser',...extra},'USER'));
 }
});
test('user-controlled role metadata does not override verified role',()=>{
 const p=normalizeVerifiedProfile({...base,role:'hospital_staff',hospital_id:'H1',user_metadata:{role:'superuser'}},'USER');
 assert.equal(p.role,'hospital_staff');assert.equal(homeForProfile(p),'/hospital');
});
test('backend verification sends the current bearer token and checks identity',async()=>{
 let request;
 const session={access_token:'FAKE-TEST-TOKEN',user:{id:'USER'}};
 const p=await fetchVerifiedProfile(session,{baseUrl:'https://backend.example.invalid/',fetcher:async(url,options)=>{
  request={url,options};return{ok:true,status:200,json:async()=>({...base,role:'car_owner',owner_id:'O1'})};
 }});
 assert.equal(request.url,'https://backend.example.invalid/api/auth/me');
 assert.equal(request.options.headers.Authorization,'Bearer FAKE-TEST-TOKEN');
 assert.equal(p.ownerId,'O1');assert.equal(p.hospitalId,null);
});
test('backend denial, outage and malformed response never produce a profile',async()=>{
 const session={access_token:'FAKE',user:{id:'USER'}};
 for(const status of [401,403,500]) await assert.rejects(fetchVerifiedProfile(session,{baseUrl:'https://backend.example.invalid',fetcher:async()=>({ok:false,status})}));
 await assert.rejects(fetchVerifiedProfile(session,{baseUrl:'https://backend.example.invalid',fetcher:async()=>({ok:true,status:200,json:async()=>{throw new SyntaxError('bad-json')}})}));
});
test('credential failures use safe messages',()=>{
 assert.match(signInError({code:'invalid_credentials'}),/incorrect/);
 assert.match(signInError({code:'email_not_confirmed'}),/Confirm/);
 assert.match(signInError({status:429}),/Too many/);
 assert.doesNotMatch(signInError({message:'secret-credential'}),/secret-credential/);
});
