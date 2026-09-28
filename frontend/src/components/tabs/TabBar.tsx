import { useRef, type KeyboardEvent, type ReactNode } from "react";

export interface TabItem<T extends string> {
  id: T;
  label: string;
}

export interface TabBarProps<T extends string> {
  label: string;
  tabs: readonly TabItem<T>[];
  active: T;
  onChange: (id: T) => void;
  children: ReactNode;
}

/**
 * Tabs with their panel (WAI-ARIA tabs pattern): arrow keys, Home and End move between tabs,
 * and only the active tab is in the Tab order.
 */
export function TabBar<T extends string>({ label, tabs, active, onChange, children }: TabBarProps<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const last = tabs.length - 1;
    const next = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: last }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    const wrapped = next > last ? 0 : next < 0 ? last : next;
    const tab = tabs[wrapped];
    if (tab) {
      onChange(tab.id);
      refs.current[wrapped]?.focus();
    }
  }

  return (
    <div className="tabbar">
      <div className="tabbar__list" role="tablist" aria-label={label}>
        {tabs.map((tab, index) => {
          const selected = tab.id === active;
          return (
            <button
              key={tab.id}
              ref={(el) => {
                refs.current[index] = el;
              }}
              type="button"
              role="tab"
              id={`tab-${tab.id}`}
              aria-selected={selected}
              aria-controls={`tabpanel-${tab.id}`}
              tabIndex={selected ? 0 : -1}
              className={selected ? "tabbar__tab tabbar__tab--active" : "tabbar__tab"}
              onClick={() => onChange(tab.id)}
              onKeyDown={(event) => onKeyDown(event, index)}
            >
              {tab.label}
            </button>
          );
        })}
      </div>
      <div
        className="tabbar__panel"
        role="tabpanel"
        id={`tabpanel-${active}`}
        aria-labelledby={`tab-${active}`}
        tabIndex={0}
      >
        {children}
      </div>
    </div>
  );
}
