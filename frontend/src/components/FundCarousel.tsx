import React, { useState, useEffect, useCallback } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Loader2, ChevronLeft, ChevronRight } from 'lucide-react';

interface FundCarouselProps {
  fundsList: string[];
  onFundClick: (fundName: string) => void;
}

export default function FundCarousel({ fundsList, onFundClick }: FundCarouselProps) {
  const [displayIndex, setDisplayIndex] = useState(0);
  const [fetchIndex, setFetchIndex] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const [historicalData, setHistoricalData] = useState<any[]>([]);
  const [currentRisk, setCurrentRisk] = useState<string>("Very High");
  const [isError, setIsError] = useState(false);
  const [isRealData, setIsRealData] = useState(false);

  const handlePrevious = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setFetchIndex((current) => (current - 1 + fundsList.length) % fundsList.length);
  }, [fundsList.length]);

  const handleNext = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setFetchIndex((current) => (current + 1) % fundsList.length);
  }, [fundsList.length]);

  // Auto-Rotation Engine
  useEffect(() => {
    if (isPaused || fundsList.length === 0) return;

    const timer = setInterval(() => {
      setFetchIndex((current) => (current + 1) % fundsList.length);
    }, 5000);
    return () => clearInterval(timer);
  }, [isPaused, fundsList.length]);

  // Fix out-of-bounds if fundsList shrinks (e.g. search filtering)
  useEffect(() => {
    if (fundsList.length > 0 && fetchIndex >= fundsList.length) {
      setFetchIndex(0);
      setDisplayIndex(0);
    }
  }, [fundsList.length, fetchIndex]);

  // Data Fetching
  useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    let isCurrent = true;
    
    const fetchHistory = async (isRetry = false) => {
      if (fundsList.length === 0) return;
      
      // Prevent out of bounds if state hasn't caught up yet
      if (fetchIndex >= fundsList.length) return;
      
      const targetFund = fundsList[fetchIndex];
      
      if (!isRetry) {
        setIsError(false);
        // Temporarily clear risk so the UI animates down and back up, 
        // proving to the user that it is actively fetching new data
        setCurrentRisk(""); 
      }
      try {
        const res = await fetch(`http://localhost:8000/api/funds/history?fund_name=${encodeURIComponent(targetFund)}`);
        if (!isCurrent) return; // Ignore if fetchIndex changed
        
        if (res.ok) {
          const data = await res.json();
          setHistoricalData(data.history || []);
          setIsRealData(data.is_real_data || false);
          setDisplayIndex(fetchIndex); // Atomically update UI
          
          if (data.risk_level) {
            // Force a slight delay so the drop-to-zero animation is perfectly visible
            // to the user, proving that the component is actually updating even if 
            // the new risk level is identically 'Very High'.
            setTimeout(() => {
              if (isCurrent) setCurrentRisk(data.risk_level);
            }, 300);
          }
          
          // Background polling if it fell back to mock data
          if (data.is_real_data === false) {
            timeoutId = setTimeout(() => {
              if (isCurrent) fetchHistory(true);
            }, 3000);
          }
        } else {
          if (!isRetry) setIsError(true);
          setDisplayIndex(fetchIndex); // Update UI even on error so it doesn't get stuck
        }
      } catch (err) {
        if (!isCurrent) return;
        console.error("Failed to fetch history", err);
        if (!isRetry) setIsError(true);
        setDisplayIndex(fetchIndex); // Update UI even on error so it doesn't get stuck
      }
    };
    
    fetchHistory();
    
    return () => {
      isCurrent = false;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [fetchIndex, fundsList]);

  if (fundsList.length === 0) return null;

  const currentFundName = fundsList[displayIndex];
  const currentNav = historicalData.length > 0 ? historicalData[historicalData.length - 1].nav : 0;
  const previousNav = historicalData.length > 1 ? historicalData[historicalData.length - 2].nav : currentNav;
  const isPositive = currentNav >= previousNav;

  return (
    <div 
      className="w-full h-full flex flex-col justify-center max-w-4xl mx-auto cursor-pointer relative group transition-transform duration-500 hover:scale-[1.02]"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      onClick={() => onFundClick(currentFundName)}
    >
      <div className="absolute inset-0 bg-gradient-to-tr from-[#00D09C]/0 to-[#00D09C]/0 group-hover:from-[#00D09C]/5 group-hover:to-transparent rounded-3xl transition-colors duration-500"></div>
      
      <div className="z-10 px-8 pb-4 relative mt-10">
        {/* Navigation Arrows */}
        <button 
          onClick={handlePrevious}
          className="absolute left-0 top-1/2 -translate-y-1/2 -ml-4 w-10 h-10 rounded-full bg-white dark:bg-[#1F2937] border border-[#E5E7EB] dark:border-[#374151] flex items-center justify-center text-[#4B5563] dark:text-[#D1D5DB] hover:bg-[#F3F4F6] dark:hover:bg-[#374151] hover:text-[#00D09C] transition-all shadow-md z-20 group-hover:opacity-100 opacity-0"
        >
          <ChevronLeft size={20} />
        </button>
        <button 
          onClick={handleNext}
          className="absolute right-0 top-1/2 -translate-y-1/2 -mr-4 w-10 h-10 rounded-full bg-white dark:bg-[#1F2937] border border-[#E5E7EB] dark:border-[#374151] flex items-center justify-center text-[#4B5563] dark:text-[#D1D5DB] hover:bg-[#F3F4F6] dark:hover:bg-[#374151] hover:text-[#00D09C] transition-all shadow-md z-20 group-hover:opacity-100 opacity-0"
        >
          <ChevronRight size={20} />
        </button>

        <div className="flex flex-col md:flex-row md:justify-between md:items-start gap-4">
          <h2 className="text-4xl md:text-5xl font-extrabold text-[#111827] dark:text-[#F3F4F6] tracking-tight mb-2 transition-all duration-300">
            {currentFundName}
          </h2>
          
          {/* Badge moved to flex flow to avoid overlap */}
          <div className={`transition-opacity duration-300 ${isPaused ? 'opacity-100' : 'opacity-0'}`}>
            <div className="bg-[#111827] text-white text-xs font-bold px-4 py-2 rounded-full shadow-lg flex items-center gap-1.5 animate-pulse ring-4 ring-[#00D09C]/20 whitespace-nowrap">
              <span>Click to analyze</span>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m9 18 6-6-6-6"/></svg>
            </div>
          </div>
        </div>
        
        <div className="flex items-end gap-3 mt-4">
          <span className="text-3xl font-semibold text-[#374151] dark:text-[#E5E7EB] flex items-center gap-2">
            ₹{(isError || historicalData.length === 0) ? "N/A" : currentNav.toFixed(2)}
            {!isError && historicalData.length > 0 && isRealData && (
              <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded-full border border-green-200 shadow-[0_0_8px_rgba(34,197,94,0.4)] flex items-center gap-1.5 font-bold" title="Live verified market data.">
                <span className="w-1.5 h-1.5 rounded-full bg-green-600 animate-pulse"></span>
                Live
              </span>
            )}
          </span>
          {!isError && historicalData.length > 1 && (
            <span className={`text-lg font-medium mb-1 ${isPositive ? 'text-[#00D09C]' : 'text-red-500'}`}>
              {isPositive ? '+' : ''}{(currentNav - previousNav).toFixed(2)} ({((currentNav - previousNav)/previousNav * 100).toFixed(2)}%)
            </span>
          )}
        </div>
      </div>
      
      <div className="h-[400px] w-full mt-4 relative z-10">
        {isError ? (
          <div className="absolute inset-0 flex items-center justify-center text-red-500 font-semibold">
            Failed to load chart data. Please ensure backend is running.
          </div>
        ) : historicalData.length === 0 ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 className="animate-spin text-[#00D09C]" size={32} />
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={historicalData} margin={{ top: 20, right: 0, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="colorNav" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00D09C" stopOpacity={0.4}/>
                  <stop offset="95%" stopColor="#00D09C" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <XAxis dataKey="date" hide />
              <YAxis domain={['auto', 'auto']} hide />
              <Tooltip 
                contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 8px 30px rgba(0,0,0,0.12)' }}
                itemStyle={{ color: '#00D09C', fontWeight: 'bold' }}
                labelStyle={{ color: '#6B7280', marginBottom: '4px' }}
              />
              <Area 
                type="monotone" 
                dataKey="nav" 
                stroke="#00D09C" 
                strokeWidth={4}
                fillOpacity={1} 
                fill="url(#colorNav)" 
                animationDuration={800}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="mt-8 flex justify-center gap-2 z-10 flex-wrap px-4">
        {fundsList.map((_, idx) => (
          <div 
            key={idx} 
            className={`h-1.5 rounded-full transition-all duration-300 ${idx === displayIndex ? 'w-6 bg-[#00D09C]' : 'w-2 bg-[#E5E7EB] dark:bg-[#374151]'}`}
          />
        ))}
      </div>

      {/* Riskometer */}
      <div className="mt-6 z-10 w-full max-w-sm mx-auto">
        <div className="flex w-full h-2 rounded-full overflow-hidden shadow-inner">
          {[
            { level: "Low", color: "#00D09C" },
            { level: "Low to Moderate", color: "#84CC16" },
            { level: "Moderate", color: "#FACC15" },
            { level: "Moderately High", color: "#F59E0B" },
            { level: "High", color: "#EA580C" },
            { level: "Very High", color: "#EF4444" }
          ].map((r) => (
            <div 
              key={r.level}
              className={`flex-1 transition-all duration-700 ease-in-out ${
                currentRisk === r.level 
                  ? "opacity-100 scale-y-125 z-10" 
                  : "opacity-30 scale-y-100"
              }`}
              style={{ 
                backgroundColor: r.color,
                boxShadow: currentRisk === r.level ? `0 0 12px ${r.color}80` : 'none'
              }}
              title={r.level}
            />
          ))}
        </div>
        <div className="text-center mt-3 text-[13px] font-semibold text-[#4B5563] dark:text-[#9CA3AF] tracking-wide">
          Risk Level: <span style={{ 
            color: [
              { level: "Low", color: "#00D09C" },
              { level: "Low to Moderate", color: "#84CC16" },
              { level: "Moderate", color: "#FACC15" },
              { level: "Moderately High", color: "#F59E0B" },
              { level: "High", color: "#EA580C" },
              { level: "Very High", color: "#EF4444" }
            ].find(r => r.level === currentRisk)?.color || "#EF4444"
          }}>{currentRisk}</span>
        </div>
      </div>
      
      {/* The absolute badge was removed and placed inside the title flex container */}
    </div>
  );
}
