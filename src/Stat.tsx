import React from 'react';
export function Stat({
  icon,
  label,
  value,
  note
}: any) {
  return <div className="stat-card"><div className="stat-top"><span>{label}</span><div>{React.cloneElement(icon, {
          size: 16
        })}</div></div><strong>{value}</strong><small>{note}</small></div>;
}
