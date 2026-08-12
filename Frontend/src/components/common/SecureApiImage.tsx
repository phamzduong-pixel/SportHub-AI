import { useEffect, useState } from 'react';
import { apiBlob } from '@/services/apiClient';

export function SecureApiImage({ src, alt, className }: { src?: string; alt: string; className?: string }) {
  const [url, setUrl] = useState<string>();
  useEffect(() => {
    if (!src) { setUrl(undefined); return; }
    let active = true; let objectUrl: string | undefined;
    apiBlob(src.replace(/^\/api/, '')).then((blob) => {
      objectUrl = URL.createObjectURL(blob);
      if (active) setUrl(objectUrl); else URL.revokeObjectURL(objectUrl);
    }).catch(() => setUrl(undefined));
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [src]);
  return url ? <img src={url} alt={alt} className={className} /> : <div className={className + ' grid place-items-center bg-slate-100 text-xs text-slate-400'}>Đang tải ảnh</div>;
}