import React from 'react';

export default function Toast({ msg }) {
  if (!msg) return null;
  return <div className="toast show">{msg}</div>;
}