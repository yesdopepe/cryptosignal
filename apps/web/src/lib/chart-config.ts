'use client';

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  TimeScale,
} from 'chart.js';
import 'chartjs-adapter-date-fns';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  TimeScale
);

// Default chart options for dark theme
export const defaultOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: {
        color: 'rgb(156, 163, 175)', // text-gray-400
      },
    },
    tooltip: {
      backgroundColor: 'rgb(31, 41, 55)', // bg-gray-800
      titleColor: 'rgb(255, 255, 255)',
      bodyColor: 'rgb(209, 213, 219)', // text-gray-300
      borderColor: 'rgb(55, 65, 81)', // border-gray-700
      borderWidth: 1,
    },
  },
  scales: {
    x: {
      grid: {
        color: 'rgba(75, 85, 99, 0.3)', // gray-600 with opacity
      },
      ticks: {
        color: 'rgb(156, 163, 175)', // text-gray-400
      },
    },
    y: {
      grid: {
        color: 'rgba(75, 85, 99, 0.3)',
      },
      ticks: {
        color: 'rgb(156, 163, 175)',
      },
    },
  },
};

// Chart colors
export const chartColors = {
  bullish: {
    background: 'rgba(34, 197, 94, 0.2)', // green-500
    border: 'rgb(34, 197, 94)',
  },
  bearish: {
    background: 'rgba(239, 68, 68, 0.2)', // red-500
    border: 'rgb(239, 68, 68)',
  },
  neutral: {
    background: 'rgba(234, 179, 8, 0.2)', // yellow-500
    border: 'rgb(234, 179, 8)',
  },
  primary: {
    background: 'rgba(59, 130, 246, 0.2)', // blue-500
    border: 'rgb(59, 130, 246)',
  },
  secondary: {
    background: 'rgba(168, 85, 247, 0.2)', // purple-500
    border: 'rgb(168, 85, 247)',
  },
};

export { ChartJS };
