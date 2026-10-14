import { useEffect, useRef, useSyncExternalStore } from 'react';
import { createPortal } from 'react-dom';
import { pendingRequests, subscribeRequests } from './request-loading';
import { t, useLocale } from './i18n';
export function FullScreenLoading() {
  useLocale();
  const dialog = useRef<HTMLDialogElement>(null);
  const pending = useSyncExternalStore(subscribeRequests, pendingRequests, () => 0);
  const visible = pending > 0;
  useEffect(() => {
    if (!visible) return;
    if (dialog.current && !dialog.current.open) dialog.current.showModal();
    const root = document.getElementById('root');
    if (!root) return;
    const previous = root.inert;
    root.inert = true;
    root.setAttribute('aria-busy', 'true');
    return () => {
      root.inert = previous;
      root.removeAttribute('aria-busy');
    };
  }, [visible]);
  return visible
    ? createPortal(
        <dialog
          ref={dialog}
          className="fullscreen-loading"
          aria-label={t('正在加载…')}
          onCancel={(event) => event.preventDefault()}
        >
          <div role="status" aria-live="polite">
            <div className="loading-card">
              <span className="loading-spinner" aria-hidden="true" />
              <span>{t('正在加载…')}</span>
            </div>
          </div>
        </dialog>,
        document.body,
      )
    : null;
}
