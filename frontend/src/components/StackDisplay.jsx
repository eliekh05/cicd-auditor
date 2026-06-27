const CATS = [
  { key: "languages",      label: "Languages",       cls: "chip-blue"   },
  { key: "frameworks",     label: "Frameworks",      cls: "chip-purple" },
  { key: "runtimes",       label: "Runtimes",        cls: ""            },
  { key: "build_tools",    label: "Build tools",     cls: ""            },
  { key: "test_frameworks",label: "Test",            cls: "chip-green"  },
  { key: "containers",     label: "Containers",      cls: "chip-amber"  },
  { key: "deploy_targets", label: "Deploy targets",  cls: "chip-amber"  },
];

function label(item) {
  if (item.value && item.value.length < 40) return item.value;
  return item.detail?.slice(0, 36) ?? "—";
}

export default function StackDisplay({ stack }) {
  const any = CATS.some(({ key }) => stack[key]?.length > 0);
  if (!any) return (
    <p style={{ color: "var(--text-3)", fontSize: "0.85rem" }}>
      Nothing obvious detected — the repo may use a language or build system we don't recognise yet.
    </p>
  );

  return (
    <div>
      {CATS.map(({ key, label: lbl, cls }) => {
        const items = stack[key];
        if (!items?.length) return null;
        return (
          <div key={key} className="stack-group">
            <div className="stack-label">{lbl}</div>
            <div className="chips">
              {items.map((item, i) => (
                <span
                  key={i}
                  className={`chip ${cls}`}
                  title={`${item.source} · ${Math.round(item.score * 100)}%`}
                >
                  {label(item)}
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
