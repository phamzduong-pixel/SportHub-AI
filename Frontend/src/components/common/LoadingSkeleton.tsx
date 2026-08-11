import { cn } from '@/utils/cn';
export function LoadingSkeleton({ className, lines = 1 }: { className?: string; lines?: number }) { return <div className={cn('animate-pulse space-y-2', className)}>{Array.from({ length: lines }).map((_, index) => <div key={index} className="h-4 rounded bg-slate-200 last:w-3/4" />)}</div>; }
