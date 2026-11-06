import React from 'react';
type StatProps = {icon: React.ReactElement<{size?: number}>; label: string; value: number | string; note: string};
export function Stat({icon, label, value, note}: StatProps) {
  return (
    <div className="stat-card">
      <div className="stat-top">
        <span>{label}</span>
        <div>
          {React.cloneElement(icon, {
            size: 16,
          })}
        </div>
      </div>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}
