import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loginSchema, reviewSchema } from '../lib/validation.ts';
test('login rejects malformed email and empty passwords',()=>{
 assert.equal(loginSchema.safeParse({email:'bad',password:'x'}).success,false);
 assert.equal(loginSchema.safeParse({email:'user@example.com',password:''}).success,false);
 assert.equal(loginSchema.safeParse({email:'user@example.com',password:'valid-password'}).success,true);
});
test('review requires a reason and explicit human confirmation',()=>{
 assert.equal(reviewSchema.safeParse({comment:'Reviewed exact evidence',confirmed:false}).success,false);
 assert.equal(reviewSchema.safeParse({comment:'ok',confirmed:true}).success,false);
 assert.equal(reviewSchema.safeParse({comment:'Reviewed exact evidence',confirmed:true}).success,true);
});
