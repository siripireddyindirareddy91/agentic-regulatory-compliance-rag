import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'ComplyIntel AI · Compliance Intelligence', description: 'Evidence-led regulatory monitoring, agent investigations and human decisions.' };
export default function Layout({ children }: {children: React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
