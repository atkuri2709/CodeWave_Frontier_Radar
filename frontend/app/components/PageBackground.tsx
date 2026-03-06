'use client';

export function PageBackground() {
  return (
    <div className="fixed inset-0 z-0 overflow-hidden" aria-hidden>
      <div className="absolute inset-0" style={{ background: '#f0f1f5' }} />
      <div className="absolute -top-[25%] -right-[12%] h-[70vh] w-[50vw] opacity-40"
        style={{ background: 'radial-gradient(ellipse at center, rgba(157,170,242,0.18) 0%, transparent 60%)', animation: 'float 22s ease-in-out infinite' }} />
      <div className="absolute -bottom-[15%] -left-[8%] h-[55vh] w-[40vw] opacity-35"
        style={{ background: 'radial-gradient(ellipse at center, rgba(255,106,61,0.08) 0%, transparent 60%)', animation: 'float 26s ease-in-out infinite reverse' }} />
      <div className="absolute top-[45%] right-[25%] h-[35vh] w-[25vw] opacity-25"
        style={{ background: 'radial-gradient(ellipse at center, rgba(244,219,125,0.12) 0%, transparent 60%)', animation: 'float 18s ease-in-out infinite 3s' }} />
      <div className="absolute inset-0 opacity-[0.25]"
        style={{ backgroundImage: 'radial-gradient(rgba(26,34,56,0.06) 1px, transparent 1px)', backgroundSize: '24px 24px' }} />
    </div>
  );
}
