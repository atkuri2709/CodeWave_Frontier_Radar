import type { Metadata } from 'next';
import './globals.css';
import { Nav } from './components/Nav';
import { PageBackground } from './components/PageBackground';
import { Providers } from './providers';

export const metadata: Metadata = {
  title: 'Frontier AI Radar',
  description: 'Daily Multi-Agent Intelligence System',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="relative min-h-screen antialiased">
        <Providers>
          <PageBackground />
          <Nav />
          <main className="relative z-10 mx-auto max-w-6xl px-4 py-6 md:py-8">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
