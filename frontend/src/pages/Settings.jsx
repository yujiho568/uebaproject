import React, { useEffect, useMemo, useState } from 'react';

function Settings() {
  const API_BASE = '/api/v1';

  const [me, setMe] = useState(null);
  const [meLoading, setMeLoading] = useState(true);
  const [meErr, setMeErr] = useState(null);

  const [creds, setCreds] = useState([]);     // [{ name, region, created_at, access_key_id_last4, has_secret }]
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);
  const [msg, setMsg] = useState(null);       // {type:'success'|'error'|'info', text}

  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  const authHeader = token ? { Authorization: `Bearer ${token}` } : {};

  // 1) 로그인 사용자
  useEffect(() => {
    const run = async () => {
      setMeLoading(true);
      setMeErr(null);
      try {
        const res = await fetch(`${API_BASE}/users/me`, {
          headers: { 'Content-Type': 'application/json', ...authHeader },
          credentials: 'include',
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data?.detail || `me 실패 (${res.status})`);
        setMe(data);
      } catch (e) {
        setMeErr(e.message);
      } finally {
        setMeLoading(false);
      }
    };
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 2) 자격증명 목록
  const loadCreds = async () => {
    if (!me?.id) return;
    setLoading(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(`${API_BASE}/credentials/${me.id}/list`, {
        headers: { 'Content-Type': 'application/json', ...authHeader },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || `credentials 실패 (${res.status})`);
      setCreds(data || []);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (me?.id) loadCreds();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me?.id]);

  // 3) 삭제
  const handleDelete = async (name) => {
    if (!me?.id || !name) return;
    if (!window.confirm(`정말로 '${name}' 자격증명을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`)) return;

    setMsg({ type: 'info', text: `'${name}' 삭제 중...` });
    try {
      const res = await fetch(`${API_BASE}/credentials/${me.id}/${encodeURIComponent(name)}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json', ...authHeader },
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || `삭제 실패 (${res.status})`);
      }
      setMsg({ type: 'success', text: `'${name}' 삭제 완료` });
      // 목록 갱신
      loadCreds();
    } catch (e) {
      setMsg({ type: 'error', text: e.message });
    }
  };

  const fmtDate = (iso) => {
    if (!iso) return '-';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso);
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };

  if (meLoading) {
    return (
      <div style={{ padding: 20 }}>
        <h1>Settings</h1>
        <p>사용자 정보를 불러오는 중...</p>
      </div>
    );
  }
  if (meErr) {
    return (
      <div style={{ padding: 20 }}>
        <h1>Settings</h1>
        <p style={{ color: '#ef4444' }}>오류: {meErr}</p>
      </div>
    );
  }

  return (
    <div style={{ padding: 20, maxWidth: 1000, margin: '0 auto' }}>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: 25 }}>AWS Credentials</h1>
      </div>

      {err && (
        <div style={{ marginBottom: 12, padding: '8px 10px', borderRadius: 8, border: '1px solid #ef4444', background: '#fee2e2', color: '#991b1b' }}>
          {err}
        </div>
      )}
      {msg && (
        <div style={{
          marginBottom: 12, padding: '8px 10px', borderRadius: 8,
          border: `1px solid ${msg.type === 'error' ? '#ef4444' : msg.type === 'info' ? '#60a5fa' : '#10b981'}`,
          background: msg.type === 'error' ? '#fee2e2' : msg.type === 'info' ? '#dbeafe' : '#d1fae5',
          color: msg.type === 'error' ? '#991b1b' : msg.type === 'info' ? '#1e3a8a' : '#065f46'
        }}>
          {msg.text}
        </div>
      )}

      <div style={{ overflowX: 'auto', border: '1px solid #e5e7eb', borderRadius: 12 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead style={{ background: '#f9fafb' }}>
            <tr>
              <th style={th}>이름</th>
              <th style={th}>리전</th>
              <th style={th}>Access Key (마스킹)</th>
              <th style={th}>생성일</th>
              <th style={th}>작업</th>
            </tr>
          </thead>
          <tbody>
            {(!creds || creds.length === 0) ? (
              <tr>
                <td colSpan={6} style={{ padding: 16, textAlign: 'center', color: '#6b7280' }}>
                  등록된 자격증명이 없습니다.
                </td>
              </tr>
            ) : (
              creds.map((c) => (
                <tr key={c.name} style={{ borderTop: '1px solid #f3f4f6' }}>
                  <td style={td}><b>{c.name}</b></td>
                  <td style={td}>{c.region || '-'}</td>
                  <td style={{ ...td, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace' }}>
                    {/* 백엔드에서 access_key_id_last4를 내려준다고 가정 */}
                    {c.access_key_id_last4 ? `**** **** **** ${c.access_key_id_last4}` : '-'}
                  </td>
                  <td style={td}>{fmtDate(c.created_at)}</td>
                  <td style={td}>
                    <button
                      onClick={() => handleDelete(c.name)}
                      style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid #ef4444', background: '#fee2e2', color: '#991b1b' }}
                    >
                      삭제
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* <p style={{ marginTop: 10, fontSize: 12, color: '#6b7280' }}>
        * 비밀키는 화면에 표시되지 않습니다. 삭제 시 되돌릴 수 없으니 주의하세요.
      </p> */}
    </div>
  );
}

const th = { textAlign: 'left', padding: 10, borderBottom: '1px solid #e5e7eb', whiteSpace: 'nowrap' };
const td = { padding: 10, verticalAlign: 'top' };

export default Settings;
