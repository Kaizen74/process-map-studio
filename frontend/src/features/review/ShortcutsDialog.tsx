import { Button, Dialog } from "../../components/common";
import { SHORTCUTS } from "../../lib/shortcuts";

/** The keyboard shortcut list, opened with "?" (PRD §5.8). */
export function ShortcutsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
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
        {SHORTCUTS.map((s) => (
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
