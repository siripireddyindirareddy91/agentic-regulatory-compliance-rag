import { z } from 'zod';
export const loginSchema=z.object({email:z.string().email('Enter a valid email'),password:z.string().min(1,'Enter your password')});
export const reviewSchema=z.object({comment:z.string().min(5),confirmed:z.literal(true)});
