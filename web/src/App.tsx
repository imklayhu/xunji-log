import { useCallback, useEffect, useState } from "react";
import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import {
  Analysis,
  SyncStatus,
  fetchAnalysis,
  fetchSyncStatus,
  refreshAnalysis,
  triggerSync,
} from "./api";
import Overview from "./pages/Overview";
import FatLoss from "./pages/FatLoss";
import Muscle from "./pages/Muscle";
import Rhythm from "./pages/Rhythm";
import Movements from "./pages/Movements";
import Calendar from "./pages/Calendar";

export default function App() {
  const [data, setData] = useState<Analysis | null>(null);
  const [sync, setSync] = useState<SyncStatus | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [analysis, status] = await Promise.all([
        fetchAnalysis(),
        fetchSyncStatus().catch(() => null),
      ]);
      setData(analysis);
      setSync(status);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRefresh = async () => {
    try {
      await refreshAnalysis();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "刷新失败");
    }
  };

  const onSync = async () => {
    setSyncing(true);
    setError("");
    try {
      const status = await triggerSync();
      setSync(status);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "同步失败");
    } finally {
      setSyncing(false);
    }
  };

  if (loading) return <div className="loading">加载训练数据中…</div>;
  if (error || !data) return <div className="error">{error || "无数据"}</div>;

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route
          index
          element={
            <Overview
              data={data}
              sync={sync}
              syncing={syncing}
              onRefresh={onRefresh}
              onSync={onSync}
            />
          }
        />
        <Route path="fat-loss" element={<FatLoss data={data} />} />
        <Route path="muscle" element={<Muscle data={data} />} />
        <Route path="rhythm" element={<Rhythm data={data} />} />
        <Route path="movements" element={<Movements data={data} />} />
        <Route path="calendar" element={<Calendar data={data} />} />
      </Route>
    </Routes>
  );
}
