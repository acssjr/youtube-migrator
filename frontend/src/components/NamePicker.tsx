import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown } from 'lucide-react';

interface Props { label: string; value: string; options: string[]; disabled?: boolean; onChange: (value: string) => void }

export function NamePicker({ label, value, options, disabled, onChange }: Props) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [filtering, setFiltering] = useState(false);
  const [bounds, setBounds] = useState({ left: 0, top: 0, width: 0, maxHeight: 260 });
  const normalize = (text: string) => text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase();
  const matches = options.filter(option => normalize(option).includes(normalize(value)));
  const shown = filtering ? matches : options;
  useEffect(() => {
    if (!open || disabled) return;
    const place = () => {
      const rect = input.current?.getBoundingClientRect();
      if (!rect) return;
      const below = window.innerHeight - rect.bottom - 12;
      const above = below < 170 && rect.top > below;
      const height = Math.min(260, Math.max(80, above ? rect.top - 12 : below));
      setBounds({ left: rect.left, width: rect.width, top: above ? rect.top - height - 6 : rect.bottom + 6, maxHeight: height });
    };
    place();
    const outside = (event: PointerEvent) => { if (!input.current?.parentElement?.contains(event.target as Node) && !popup.current?.contains(event.target as Node)) setOpen(false); };
    window.addEventListener('resize', place); window.addEventListener('scroll', place, true); document.addEventListener('pointerdown', outside);
    return () => { window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true); document.removeEventListener('pointerdown', outside); };
  }, [open, disabled]);
  useEffect(() => { if (disabled) setOpen(false); }, [disabled]);
  useEffect(() => { if (active >= 0) popup.current?.querySelector(`[data-option="${active}"]`)?.scrollIntoView({ block: 'nearest' }); }, [active]);
  const choose = (name: string) => { onChange(name); setOpen(false); setActive(-1); input.current?.focus(); };
  return <div className="name-picker">
    <input ref={input} aria-label={label} role="combobox" aria-autocomplete="list" aria-expanded={open && !disabled} aria-controls={open ? id : undefined} aria-activedescendant={open && active >= 0 ? `${id}-${active}` : undefined}
      value={value} disabled={disabled} placeholder="Selecione ou digite o nome" autoComplete="off"
      onClick={() => { setOpen(true); setFiltering(false); setActive(-1); }} onBlur={() => setOpen(false)} onChange={event => { onChange(event.target.value); setOpen(true); setFiltering(true); setActive(-1); }}
      onKeyDown={event => {
        if (event.key === 'Escape') { setOpen(false); return; }
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); setOpen(true); setActive(old => shown.length ? Math.max(0, Math.min(shown.length - 1, old + (event.key === 'ArrowDown' ? 1 : -1))) : -1); }
        if (event.key === 'Enter' && open) { event.preventDefault(); if (active >= 0 && shown[active]) choose(shown[active]); else setOpen(false); }
      }}/>
    <button type="button" tabIndex={-1} disabled={disabled} aria-label={`Opções de ${label}`} onMouseDown={event => event.preventDefault()} onClick={() => { setOpen(!open); setFiltering(false); setActive(-1); input.current?.focus(); }}><ChevronDown size={16}/></button>
    {open && !disabled && createPortal(<div ref={popup} className="name-picker-popup" style={bounds} onMouseDown={event => event.preventDefault()}>
      <div role="listbox" id={id} aria-label={label}>{shown.map((name, index) => <button type="button" id={`${id}-${index}`} data-option={index} role="option" aria-selected={name === value} className={active === index ? 'highlighted' : ''} key={name} onClick={() => choose(name)}>{name}</button>)}</div>
      {!shown.length && <p>{value ? 'Nome novo. Continue digitando para usá-lo.' : 'Digite um nome para adicionar.'}</p>}
    </div>, document.body)}
  </div>;
}
