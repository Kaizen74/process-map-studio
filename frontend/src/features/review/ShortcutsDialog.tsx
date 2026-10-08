import { Button, Dialog } from "../../components/common";
import type { Lens } from "../../lib/lens";
import { shortcutList } from "../../lib/shortcuts";

/** The keyboard shortcut list, opened with "?" (PRD §5.8). */
export function ShortcutsDialog({
  open,
  onClose,
  lenses,
}: {
  open: boolean;
  onClose: () => void;
  /** The lenses on offer (Volume and wait while System records is on). */
  lenses?: readonly { value: Lens; label: string }[];
}) {
  return (
    <Dialog
      open={open}
      title="Keyboard shortcuts"
      description="They work anywhere on the Review screen, except while you are typing in a field."
      actions={
        <Button variant="primary" onClick={onClose}>
          Close
        </Button>
      }
      onClose={onClose}
    >
      <dl className="shortcuts">
        {shortcutList(lenses).map((s) => (
          <div key={s.keys} className="shortcuts__row">
            <dt>
              <kbd className="mono">{s.keys}</kbd>
            </dt>
            <dd>{s.action}</dd>
          </div>
        ))}
      </dl>
    </Dialog>
  );
}
