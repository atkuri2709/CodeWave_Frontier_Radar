'use client';

import { Suspense, type ReactNode } from 'react';
import { NavigationLoader } from './components/NavigationLoader';
import { ToastProvider } from './components/Toast';

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <Suspense fallback={null}>
        <NavigationLoader />
      </Suspense>
      {children}
    </ToastProvider>
  );
}
