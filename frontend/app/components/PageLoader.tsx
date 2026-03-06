'use client';

export function PageLoader({ variant = 'default' }: { variant?: 'default' | 'cards' | 'list' }) {
  return (
    <div className="animate-fade-in space-y-6">
      {/* Header skeleton */}
      <div className="skeleton h-28 rounded-2xl" />

      {variant === 'cards' && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map(i => <div key={i} className="skeleton h-28 rounded-2xl" />)}
        </div>
      )}

      {variant === 'list' && (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} className="skeleton h-20 rounded-2xl" style={{ animationDelay: `${i * 0.05}s` }} />
          ))}
        </div>
      )}

      {variant === 'default' && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[1, 2, 3, 4].map(i => <div key={i} className="skeleton h-28 rounded-2xl" />)}
          </div>
          <div className="skeleton h-64 rounded-2xl" />
        </>
      )}
    </div>
  );
}
