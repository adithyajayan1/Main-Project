import { useState, useEffect } from "react";
import { S } from "../styles";
import { API_URL } from "../constants";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';
import { Line, Doughnut } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, BarElement, LineElement, PointElement, ArcElement, Title, Tooltip, Legend);

export default function ReportsPage({ user }) {
  const [chartData, setChartData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('month');

  useEffect(() => {
    setLoading(true);
    fetch(`${API_URL}/api/reports/${user.id}?period=${timeRange}`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
    })
      .then(res => res.json())
      .then(data => { setChartData(data); setLoading(false); })
      .catch(err => { console.error("Reports fetch error:", err); setLoading(false); });
  }, [user.id, timeRange]);

  const sessionsChartData = {
    labels: chartData?.labels || [],
    datasets: [{
      label: 'Sessions Completed',
      data: chartData?.sessions || [],
      backgroundColor: 'rgba(0, 230, 118, 0.2)',
      borderColor: 'rgba(0, 230, 118, 1)',
      borderWidth: 2,
      fill: true,
      tension: 0.4
    }]
  };

  const exerciseChartData = {
    labels: chartData?.exercises?.map(e => e.name.toUpperCase()) || [],
    datasets: [{
      data: chartData?.exercises?.map(e => e.count) || [],
      backgroundColor: ['#00e676', '#7c6af7', '#ff9100', '#ff1744', '#00bfa5'],
      borderWidth: 0
    }]
  };

  return (
    <div style={S.reportsPage}>
      <h1 style={{ fontFamily: "'Orbitron', sans-serif", marginBottom: 30 }}>YOUR PROGRESS</h1>
      
      {/* Time Range Selector */}
      <div style={S.timeSelector}>
        <button style={S.timeBtn(timeRange === 'week')} onClick={() => setTimeRange('week')}>WEEK</button>
        <button style={S.timeBtn(timeRange === 'month')} onClick={() => setTimeRange('month')}>MONTH</button>
        <button style={S.timeBtn(timeRange === 'year')} onClick={() => setTimeRange('year')}>YEAR</button>
      </div>

      {/* Sessions Over Time Chart */}
      <div style={S.chartCard}>
        <h2 style={S.chartTitle}>SESSIONS OVER TIME</h2>
        {loading ? (
          <div style={{ color: '#555', textAlign: 'center', padding: 40 }}>Loading...</div>
        ) : chartData?.sessions?.some(v => v > 0) ? (
          <div style={{ height: 300 }}>
            <Line data={sessionsChartData} options={{ responsive: true, maintainAspectRatio: false }} />
          </div>
        ) : (
          <div style={{ color: '#555', fontStyle: 'italic', textAlign: 'center', padding: 40 }}>Not enough data for this period.</div>
        )}
      </div>

      {/* Exercise Distribution Chart */}
      <div style={S.chartRow}>
        <div style={S.chartCard}>
          <h2 style={S.chartTitle}>DISTRIBUTION</h2>
          {loading ? (
            <div style={{ color: '#555', textAlign: 'center', padding: 40 }}>Loading...</div>
          ) : chartData?.exercises?.length > 0 ? (
            <div style={{ height: 250, display: 'flex', justifyContent: 'center' }}>
              <Doughnut data={exerciseChartData} options={{ responsive: true, maintainAspectRatio: false }} />
            </div>
          ) : (
             <div style={{ color: '#555', fontStyle: 'italic', textAlign: 'center', padding: 40 }}>Not enough data.</div>
          )}
        </div>
        
        <div style={S.chartCard}>
          <h2 style={S.chartTitle}>TOTAL STATS</h2>
          <div style={S.statItems}>
            <div style={S.statItem}>
              <span style={S.statLabel}>Total Sessions</span>
              <span style={S.statVal}>{chartData?.total_sessions || 0}</span>
            </div>
            <div style={S.statItem}>
              <span style={S.statLabel}>Total Reps</span>
              <span style={S.statVal}>{chartData?.total_reps || 0}</span>
            </div>
            <div style={S.statItem}>
              <span style={S.statLabel}>Total Time</span>
              <span style={S.statVal}>{chartData?.total_time || 0} MIN</span>
            </div>
            <div style={S.statItem}>
              <span style={S.statLabel}>Best Streak</span>
              <span style={S.statVal}>{chartData?.best_streak || 0} DAYS</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
