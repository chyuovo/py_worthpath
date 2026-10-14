import { useEffect, useState } from 'react';
import { api } from './api';
import { iconUrl } from './IconLibrary';
import { t as tr } from './i18n';
import { useToast } from './Toast';

type SharedIcon = { id: string; name: string; deletedAt: string | null };
export function SharedIconAdmin({ report }: { report: (e: unknown) => void }) {
  const [items, setItems] = useState<SharedIcon[]>([]);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('active');
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<SharedIcon | null>(null);
  const [notice, setNotice] = useState('');
  useToast(notice, 'success');
  useEffect(() => {
    let active = true;
    setLoading(true);
    const timer = setTimeout(() => {
      void api<{ items: SharedIcon[]; total: number }>('/admin/icons?' + new URLSearchParams({ q, status, offset: String(offset), limit: '50' }))
        .then((result) => { if (active) { setItems(result.items); setTotal(result.total); } })
        .catch((e) => { if (active) report(e); })
        .finally(() => { if (active) setLoading(false); });
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [q, status, offset, version]);
  async function submit() {
    if (!pending) return;
    setBusy(true);
    setNotice('');
    try {
      await api('/admin/icons/' + pending.id + (pending.deletedAt ? '/restore' : ''), pending.deletedAt ? 'POST' : 'DELETE', { confirmed: true });
      setNotice(tr(pending.deletedAt ? '共享图标已恢复' : '共享图标已软删除'));
      setPending(null); setOffset(0); setVersion((v) => v + 1);
    } catch (e) { report(e); } finally { setBusy(false); }
  }
  return <section className="panel">
    <h2>{tr('共享图标管理')} · {total}</h2>
    <p className="muted">{tr('软删除后不再出现在图标库，已使用该图标的账户继续正常显示；可随时恢复。')}</p>
    <div className="actions">
      <label className="field"><span>{tr('搜索图标名称')}</span><input type="search" value={q} maxLength={100} onChange={(e) => { setQ(e.target.value); setOffset(0); }} /></label>
      <label className="field"><span>{tr('状态')}</span><select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }}>
        <option value="active">{tr('正常')}</option><option value="deleted">{tr('已软删除')}</option><option value="all">{tr('全部')}</option>
      </select></label>
    </div>
    {loading ? <p role="status">{tr('正在加载图标…')}</p> : <div className="table-wrap"><table>
      <thead><tr><th>{tr('图标')}</th><th>{tr('名称')}</th><th>{tr('状态')}</th><th>{tr('操作')}</th></tr></thead>
      <tbody>{items.map((icon) => <tr key={icon.id}>
        <td><img src={iconUrl(icon.id)} alt="" width={40} height={40} loading="lazy" /></td>
        <td>{icon.name}</td><td>{tr(icon.deletedAt ? '已软删除' : '正常')}</td>
        <td><button className={icon.deletedAt ? 'secondary' : 'danger'} disabled={busy} onClick={() => setPending(icon)}>{tr(icon.deletedAt ? '恢复图标' : '软删除')}</button></td>
      </tr>)}</tbody>
    </table>{!items.length && <p>{tr('没有匹配的共享图标')}</p>}</div>}
    <div className="actions">
      <button className="secondary" disabled={busy || loading || offset === 0} onClick={() => setOffset((v) => Math.max(0, v - 50))}>{tr('上一页')}</button>
      <button className="secondary" disabled={busy || loading || offset + 50 >= total} onClick={() => setOffset((v) => v + 50)}>{tr('下一页')}</button>
    </div>
    {pending && <div className="veil"><section className="modal" role="dialog" aria-modal="true" aria-label={tr('确认图标操作')}>
      <h2>{tr(pending.deletedAt ? '恢复图标' : '软删除')} · {pending.name}</h2>
      <p>{tr(pending.deletedAt ? '恢复后，所有登录用户可再次搜索和使用此图标。' : '确认从共享图标库下架此图标？现有账户图标和图片文件不会被删除。')}</p>
      <div className="actions"><button className="secondary" disabled={busy} onClick={() => setPending(null)}>{tr('取消')}</button><button className={pending.deletedAt ? 'primary' : 'danger'} disabled={busy} onClick={() => void submit()}>{tr('确认')}</button></div>
    </section></div>}
  </section>;
}
