'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';

export function NavigationLoader() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prevPath = useRef(pathname);

  const startLoading = useCallback(() => {
    setVisible(true);
    setProgress(15);
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setProgress(prev => {
        if (prev >= 90) { clearInterval(timerRef.current!); return 90; }
        const increment = prev < 30 ? 8 : prev < 60 ? 4 : prev < 80 ? 1.5 : 0.5;
        return Math.min(90, prev + increment);
      });
    }, 200);
  }, []);

  const completeLoading = useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    setProgress(100);
    setTimeout(() => { setVisible(false); setProgress(0); }, 350);
  }, []);

  useEffect(() => {
    if (pathname !== prevPath.current) {
      completeLoading();
      prevPath.current = pathname;
    }
  }, [pathname, searchParams, completeLoading]);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      const anchor = (e.target as HTMLElement).closest('a');
      if (!anchor) return;
      const href = anchor.getAttribute('href');
      if (!href || href.startsWith('http') || href.startsWith('#') || href.startsWith('mailto:') || anchor.target === '_blank') return;
      if (href !== pathname) startLoading();
    };
    document.addEventListener('click', handleClick, true);
    return () => document.removeEventListener('click', handleClick, true);
  }, [pathname, startLoading]);

  if (!visible && progress === 0) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[100] h-[3px]" style={{ opacity: visible ? 1 : 0, transition: 'opacity 0.3s' }}>
      <div
        className="h-full"
        style={{
          width: `${progress}%`,
          background: 'linear-gradient(90deg, #FF6A3D, #F4DB7D)',
          boxShadow: '0 0 12px rgba(255,106,61,0.5)',
          transition: progress === 0 ? 'none' : `width ${progress === 100 ? '0.2s' : '0.4s'} ease-out`,
          borderRadius: '0 2px 2px 0',
        }}
      />
    </div>
  );
}
