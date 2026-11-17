import test from 'node:test';
import assert from 'node:assert/strict';
import {createLocalClient} from '../localClient.js';

test('local login is memory-only, password change clears reset state, logout revokes token',async()=>{
  const requests=[];
  const original=globalThis.fetch;
  globalThis.fetch=async(url,options)=>{
    requests.push({url,...options});
    const body=url.endsWith('/login')?{session:{access_token:'test-token',user:{id:'test-user'},password_change_required:true}}:{};
    return {ok:true,json:async()=>body};
  };
  try {
    const client=createLocalClient('http://local');
    assert.equal((await client.auth.getSession()).data.session,null);
    const login=await client.auth.signInWithPassword({email:'test@example.com',password:'Temporary-password'});
    assert.equal(login.data.session.password_change_required,true);
    assert.equal((await createLocalClient('http://local').auth.getSession()).data.session,null);
    const changed=await client.auth.changePassword('Temporary-password','Replacement-password');
    assert.equal(changed.password_change_required,false);
    assert.equal(requests[1].headers.Authorization,'Bearer test-token');
    await client.auth.signOut();
    assert.equal((await client.auth.getSession()).data.session,null);
    assert.equal(requests[2].url,'http://local/api/auth/logout');
    assert.equal(requests[2].keepalive,true);
  } finally {globalThis.fetch=original;}
});

test('rejected local credentials do not create a session',async()=>{
  const original=globalThis.fetch;
  globalThis.fetch=async()=>({ok:false,status:401,json:async()=>({detail:'Incorrect email or password.'})});
  try {
    const client=createLocalClient('http://local');
    const response=await client.auth.signInWithPassword({email:'test@example.com',password:'wrong'});
    assert.equal(response.error.status,401);
    assert.equal((await client.auth.getSession()).data.session,null);
  } finally {globalThis.fetch=original;}
});
