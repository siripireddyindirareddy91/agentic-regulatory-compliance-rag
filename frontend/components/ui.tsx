import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
export function cn(...inputs:ClassValue[]) {return twMerge(clsx(inputs));}
export function Button({className,variant='primary',...props}:React.ButtonHTMLAttributes<HTMLButtonElement>&{variant?:'primary'|'secondary'|'danger'}) {return <button className={cn('btn',variant,className)} {...props}/>;}
export function Badge({children,tone='neutral'}:{children:React.ReactNode;tone?:string}) {return <span className={'badge '+tone}>{children}</span>;}
export function Modal({title,children,onClose}:{title:string;children:React.ReactNode;onClose:()=>void}) {return <Dialog.Root open onOpenChange={v=>!v&&onClose()}><Dialog.Portal><Dialog.Overlay className="overlay"/><Dialog.Content className="modal"><div className="modal-head"><Dialog.Title>{title}</Dialog.Title><Dialog.Close className="icon-btn" aria-label="Close"><X size={20}/></Dialog.Close></div><Dialog.Description className="sr-only">Inspect supporting evidence and complete the selected compliance operation.</Dialog.Description>{children}</Dialog.Content></Dialog.Portal></Dialog.Root>;}
