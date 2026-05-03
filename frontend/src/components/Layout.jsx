import React from "react";

export function PageHeader({ eyebrow, title, subtitle, image }) {
  return (
    <header className="relative overflow-hidden rounded-3xl mb-10" data-testid="page-header">
      {image && (
        <div
          className="absolute inset-0 bg-cover bg-center opacity-30"
          style={{ backgroundImage: `url(${image})` }}
        />
      )}
      <div className="relative px-8 py-12 md:px-12 md:py-16 bg-gradient-to-br from-[#F4F1EA] to-transparent">
        {eyebrow && (
          <p className="text-xs tracking-[0.3em] uppercase text-[#6B7270] mb-3">
            {eyebrow}
          </p>
        )}
        <h1 className="font-serif text-4xl sm:text-5xl lg:text-6xl text-[#2D312E] leading-[1.05] tracking-tight max-w-3xl text-balance">
          {title}
        </h1>
        {subtitle && (
          <p className="mt-4 text-base md:text-lg text-[#6B7270] leading-relaxed max-w-2xl">
            {subtitle}
          </p>
        )}
      </div>
    </header>
  );
}

export function Container({ children, className = "" }) {
  return (
    <div className={`px-6 md:px-10 lg:px-14 py-8 md:py-12 ${className}`}>
      {children}
    </div>
  );
}

export function Card({ children, className = "", ...rest }) {
  return (
    <div
      className={`bg-white rounded-3xl border border-sand p-6 md:p-7 shadow-[0_1px_2px_rgba(45,49,46,0.04)] hover:shadow-md transition-all ${className}`}
      {...rest}
    >
      {children}
    </div>
  );
}

export function Eyebrow({ children }) {
  return (
    <p className="text-[11px] tracking-[0.28em] uppercase text-[#9A9F9D] mb-2">
      {children}
    </p>
  );
}
