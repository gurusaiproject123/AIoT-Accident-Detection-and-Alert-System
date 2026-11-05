import test from 'node:test';
import assert from 'node:assert/strict';
import { validateUserAssignment, publicUserRecord, canOpenSuperuser, needsAssignmentCorrection } from '../userRules.js';
import {buildSeed, ROLES, NAV_ITEMS} from '../data.js';
const hospitals=[{id:'A'},{id:'B'}];
const staff={name:'Thandi',email:'thandi@example.com',role:'hospital_staff',hospitalId:'A',status:'active'};
test('several users may share one hospital',()=>{
 for(const name of ['Thandi','Staff two','Staff three']) assert.deepEqual(validateUserAssignment({...staff,name},hospitals),{});
});
test('staff require an existing single hospital',()=>{
 for(const hospitalId of [null,'','missing',['A','B']]) assert.ok(validateUserAssignment({...staff,hospitalId},hospitals).hospitalId);
});
test('superuser has no hospital and legacy role rejected',()=>{
 assert.deepEqual(validateUserAssignment({...staff,role:'superuser',hospitalId:null},hospitals),{});
 assert.ok(validateUserAssignment({...staff,role:'superuser'},hospitals).hospitalId);
 assert.ok(validateUserAssignment({...staff,role:'unassigned'},hospitals).role);
});
test('guard rejects staff, suspended admin, and hospital-assigned admin',()=>{
 assert.equal(canOpenSuperuser(staff),false);
 assert.equal(canOpenSuperuser(null),false);
 assert.equal(canOpenSuperuser({...staff,role:'superuser',hospitalId:null}),true);
 assert.equal(canOpenSuperuser({...staff,role:'superuser'}),false);
 assert.equal(canOpenSuperuser({...staff,role:'superuser',hospitalId:null,status:'suspended'}),false);
});
test('stored records exclude passwords and tokens',()=>{
 const safe=publicUserRecord({...staff,password:'never-save',access_token:'never-save',id:'1'});
 assert.equal('password' in safe,false);assert.equal('access_token' in safe,false);
});
test('new fixtures obey confirmed relationships and demonstrate three staff',()=>{
 const seed=buildSeed();assert.deepEqual(Object.keys(ROLES).sort(),['car_owner','hospital_staff','superuser']);
 for(const u of seed.users) assert.equal(needsAssignmentCorrection(u,seed.hospitals),false);
 assert.equal(seed.users.filter(u=>u.hospitalId==='HSP-001').length,3);
});

test('superuser monitors countdowns without driving navigation',()=>{
 assert.equal(NAV_ITEMS.some(item=>item.to==='vehicle'),false);
 const pending=buildSeed().incidents.filter(i=>i.status==='cancellation_window');
 assert.ok(pending.length>0);
 for(const i of pending) {assert.equal(i.cancellation.windowSeconds,30);assert.equal(i.notifications.length,0);}
});

const owners=[{id:'O1',vehicleIds:['CAR1','CAR2']}];
const ownerUser={name:'Demo owner',email:'owner@example.com',role:'car_owner',hospitalId:null,ownerId:'O1',status:'active'};
test('owner login can link to one owner record with several cars',()=>{
 assert.deepEqual(validateUserAssignment(ownerUser,hospitals,owners),{});
 assert.equal(canOpenSuperuser(ownerUser),false);
});
test('owner requires a known owner record and cannot have a hospital',()=>{
 assert.ok(validateUserAssignment({...ownerUser,ownerId:'missing'},hospitals,owners).ownerId);
 assert.ok(validateUserAssignment({...ownerUser,hospitalId:'A'},hospitals,owners).hospitalId);
 assert.ok(validateUserAssignment(ownerUser,hospitals,[{id:'O1',vehicleIds:[]}]).ownerId);
});
test('staff and admins cannot link an owner identity; safe record keeps owner link',()=>{
 assert.ok(validateUserAssignment({...staff,ownerId:'O1'},hospitals,owners).ownerId);
 assert.equal(publicUserRecord({...ownerUser,password:'do-not-store'}).ownerId,'O1');
 assert.equal('password' in publicUserRecord({...ownerUser,password:'do-not-store'}),false);
});
