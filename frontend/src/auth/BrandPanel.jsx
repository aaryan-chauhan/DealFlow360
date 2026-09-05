import Logo from '../shared/ui/Logo'

const HIGHLIGHTS = ['Sales', 'Operations', 'Customers', 'Growth']

export default function BrandPanel() {
  return (
    <aside className="relative hidden overflow-hidden bg-ink-900 lg:flex lg:w-[42%] lg:flex-col lg:justify-between">
      <div
        className="absolute inset-0 opacity-70"
        style={{
          backgroundImage:
            'linear-gradient(160deg, rgba(11,18,32,0.35) 0%, rgba(11,18,32,0.92) 55%, rgba(11,18,32,1) 100%), linear-gradient(45deg, #16233d 0%, #1f3a63 45%, #0b1220 100%)',
        }}
      />
      <div
        className="absolute inset-0 opacity-[0.13]"
        style={{
          backgroundImage:
            'repeating-linear-gradient(90deg, rgba(255,255,255,0.7) 0 1px, transparent 1px 46px), repeating-linear-gradient(0deg, rgba(255,255,255,0.7) 0 1px, transparent 1px 38px)',
          maskImage: 'linear-gradient(to bottom, transparent 5%, black 45%, transparent 95%)',
          WebkitMaskImage: 'linear-gradient(to bottom, transparent 5%, black 45%, transparent 95%)',
        }}
      />

      <div className="relative z-10 p-10">
        <Logo />
        <p className="mt-3 text-sm text-slate-300">Smarter Deals, Stronger Growth.</p>
      </div>

      <div className="relative z-10 p-10">
        <p className="text-lg font-medium text-white">From Quote to Revenue — All in One Place</p>
        <ul className="mt-5 space-y-2.5">
          {HIGHLIGHTS.map((item) => (
            <li key={item} className="flex items-center gap-2.5 text-sm text-slate-300">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
              {item}
            </li>
          ))}
        </ul>
      </div>
    </aside>
  )
}
