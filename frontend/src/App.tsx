import { useState, useRef, useEffect } from 'react';
import { Send, Plus, Search, User, Info, ExternalLink, Menu, X, Loader2, MessageSquare, PieChart, Moon, Sun, Mic, BookmarkPlus, Trash2, ThumbsUp, ThumbsDown } from 'lucide-react';
import { LineChart, Line, BarChart, Bar, XAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer } from 'recharts';
import { motion, AnimatePresence } from 'framer-motion';
import FundCarousel from './components/FundCarousel';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'refusal';
  content: string;
  timestamp: Date;
  sourceLink?: string;
  sourceDate?: string;
}

interface ParsedMessage {
  text: string;
  followUps?: string[];
  chartData?: any;
}

const parseMessageContent = (content: string): ParsedMessage => {
  // Regex to match the full json block for parsing, allowing optional spaces and optional 'json' tag
  const fullJsonRegex = /```\s*(?:json)?\s*(\{[\s\S]*?\})\s*```/i;
  // Regex to match and hide the json block even while it's streaming
  const streamingJsonRegex = /```\s*(?:json)?\s*(?:\{[\s\S]*)?$/i;
  
  const match = content.match(fullJsonRegex);
  
  if (match) {
    let jsonStr = match[1];
    
    // Auto-fix LLM hallucination where it closes follow_up_questions array with a curly brace
    jsonStr = jsonStr.replace(/"\}\s*,/g, '"],');
    jsonStr = jsonStr.replace(/"\}\s*\}/g, '"]}');
    
    try {
      const data = JSON.parse(jsonStr);
      return {
        text: content.replace(streamingJsonRegex, '').trim(),
        followUps: data.follow_up_questions,
        chartData: data.chart_data
      };
    } catch (e) {
      console.error("Error parsing JSON block", e, "Raw:", jsonStr);
      return { text: content.replace(streamingJsonRegex, '').trim() };
    }
  }
  
  // Even if not fully matched, hide it while streaming
  return { text: content.replace(streamingJsonRegex, '').trim() };
};

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  
  // Phase 1 Features State
  const [isDarkMode, setIsDarkMode] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [savedItems, setSavedItems] = useState<Message[]>([]);
  const [activeTab, setActiveTab] = useState<'recent' | 'saved'>('recent');
  const [submittedFeedback, setSubmittedFeedback] = useState<Record<string, number>>({});

  const handleFeedback = async (msgId: string, rating: number) => {
    if (submittedFeedback[msgId]) return;
    setSubmittedFeedback(prev => ({...prev, [msgId]: rating}));
    
    try {
      await fetch("http://localhost:8000/api/chat/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message_id: msgId, rating })
      });
    } catch (e) {
      console.error("Failed to submit feedback", e);
    }
  };

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const responseTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    // Load local storage
    const savedDark = localStorage.getItem('isDarkMode');
    if (savedDark === 'true') setIsDarkMode(true);
    
    const storedSavedItems = localStorage.getItem('savedItems');
    if (storedSavedItems) {
      try {
        setSavedItems(JSON.parse(storedSavedItems));
      } catch (e) {
        console.error("Error parsing saved items", e);
      }
    }

    if (SpeechRecognition && !recognitionRef.current) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = false;
      
      recognitionRef.current.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setInput(prev => prev ? prev + ' ' + transcript : transcript);
      };

      recognitionRef.current.onerror = (event: any) => {
        console.error("Speech recognition error", event.error);
        setIsListening(false);
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
      };
    }
  }, []);

  useEffect(() => {
    localStorage.setItem('isDarkMode', String(isDarkMode));
  }, [isDarkMode]);

  useEffect(() => {
    localStorage.setItem('savedItems', JSON.stringify(savedItems));
  }, [savedItems]);

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    } else {
      setInput(''); 
      recognitionRef.current?.start();
      setIsListening(true);
    }
  };

  const toggleSaveItem = (msg: Message) => {
    setSavedItems(prev => {
      const isSaved = prev.some(item => item.id === msg.id);
      return isSaved ? prev.filter(item => item.id !== msg.id) : [...prev, msg];
    });
  };

  const scrollToBottom = () => {
    if (messages.length > 0 || isTyping) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleNewConversation = () => {
    if (responseTimeoutRef.current) {
      clearTimeout(responseTimeoutRef.current);
    }
    setMessages([]);
    setInput('');
    setIsTyping(false);
    
    // Reset scroll position to top
    const chatContainer = document.getElementById('chat-scroll-container');
    if (chatContainer) {
      chatContainer.scrollTop = 0;
    }

    if (window.innerWidth < 768) {
      setIsSidebarOpen(false);
    }
  };

  const handleSend = async (text: string = input) => {
    if (!text.trim()) return;

    if (messages.length === 0) {
      setRecentChats(prev => {
        if (!prev.includes(text.trim())) {
          return [text.trim(), ...prev];
        }
        return prev;
      });
    }

    const newMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date()
    };

    setMessages(prev => [...prev, newMsg]);
    setInput('');
    setIsTyping(true);

    // Fetch from real backend
    try {
      const response = await fetch("http://localhost:8000/api/chat/stream", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          thread_id: "default_user",
          message: newMsg.content
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) {
        throw new Error("No response body stream.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      const replyId = (Date.now() + 1).toString();
      let streamedContent = "";

      // Initialize the empty message in the state
      setMessages(prev => [...prev, {
        id: replyId,
        role: 'assistant',
        content: "",
        timestamp: new Date(),
        sourceLink: "https://www.amfiindia.com/investor-corner",
        sourceDate: new Date().toISOString().split('T')[0]
      }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        streamedContent += chunk;

        // Check for refusal logic on the fly
        let currentRole: 'assistant' | 'refusal' = 'assistant';
        if (streamedContent.toLowerCase().includes('cannot provide investment advice') || 
            streamedContent.toLowerCase().includes('consult a registered financial advisor') || 
            streamedContent.toLowerCase().includes('i cannot provide')) {
           currentRole = 'refusal';
        }

        // Update the specific message with accumulated content
        setMessages(prev => prev.map(msg => 
          msg.id === replyId 
            ? { ...msg, content: streamedContent, role: currentRole }
            : msg
        ));
      }
      
    } catch (error) {
      console.error("Error communicating with backend:", error);
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        content: "I'm having trouble connecting to the backend server. Please make sure the Python API is running on localhost:8000.",
        role: 'refusal',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSend();
    }
  };

  const exampleChips = [
    "What is the expense ratio of HDFC Flexi Cap Fund?",
    "What is the minimum SIP amount?",
    "What is the benchmark index?",
    "Tell me about HDFC Small Cap performance"
  ];

  const supportedFunds = [
    "HDFC Focused Fund",
    "HDFC Small Cap Fund",
    "HDFC Mid-Cap Fund",
    "HDFC Equity Fund",
    "HDFC Large and Mid Cap Fund",
    "HDFC Balanced Advantage Fund",
    "HDFC Multi Cap Fund",
    "HDFC Defence Fund",
    "HDFC Pharma and Healthcare Fund",
    "HDFC Technology Fund",
    "HDFC Value Fund",
    "HDFC Manufacturing Fund",
    "HDFC Transportation and Logistics Fund",
    "HDFC NIFTY 50 Index Fund",
    "HDFC BSE Sensex Index Fund",
    "HDFC NIFTY Next 50 Index Fund",
    "HDFC NIFTY100 Quality 30 Index Fund",
    "HDFC NIFTY100 Low Volatility 30 Index Fund",
    "HDFC NIFTY200 Momentum 30 Index Fund",
    "HDFC Short Term Opportunities Fund",
    "HDFC Liquid Fund",
    "HDFC Money Market Fund",
    "HDFC Ultra Short Term Fund",
    "HDFC Low Duration Fund",
    "HDFC Medium Term Debt Fund",
    "HDFC Gold ETF Fund of Fund",
    "HDFC Silver ETF Fund of Fund",
    "HDFC Taxsaver Fund"
  ];

  const filteredFunds = supportedFunds.filter(fund => 
    fund.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const baseMockChats = [
    "What is the NAV of HDFC Flexi Cap Fund?",
    "What is the minimum SIP for Liquid Fund?",
    "What is the expense ratio?",
    "Should I invest in HDFC mutual funds?",
    "What are the tax benefits of ELSS funds?",
    "Tell me about HDFC Small Cap performance",
    "How to start an SIP online?",
    "What is benchmark index?"
  ];

  const [recentChats, setRecentChats] = useState<string[]>(baseMockChats);

  // Derive active chat title for the sidebar
  const activeChatTitle = messages.length > 0 ? messages[0].content : null;

  const displayChats = recentChats;

  return (
    <div className={`${isDarkMode ? 'dark' : ''} flex flex-col h-screen w-full bg-[#F7F8FA] dark:bg-[#0B0F19] text-[#111827] dark:text-[#F3F4F6] font-sans overflow-hidden transition-colors`}>
      
      {/* Sticky Header with Glassmorphism */}
      <header className="h-[64px] shrink-0 bg-white/85 dark:bg-[#111827]/85 backdrop-blur-md border-b border-[#E5E7EB] dark:border-[#1F2937] flex items-center justify-between px-4 md:px-6 z-20 shadow-[0_1px_3px_rgba(0,0,0,0.02)] sticky top-0 transition-colors">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="md:hidden p-2 -ml-2 text-[#6B7280] hover:bg-[#F3F4F6] rounded-full transition-colors"
            aria-label="Toggle Menu"
          >
            {isSidebarOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
          <div className="flex items-center gap-3 cursor-pointer">
            <img src="/groww-logo.png" alt="Groww Logo" className="w-9 h-9 object-contain rounded-full shadow-sm" />
            <div className="hidden sm:flex flex-col">
              <h1 className="font-semibold text-[16px] leading-tight tracking-tight text-[#111827] dark:text-[#F3F4F6]">Groww Mutual Fund Assistant</h1>
              <span className="text-[10px] font-bold text-[#00D09C] uppercase tracking-wider mt-0.5">Powered by RAG</span>
            </div>
          </div>
        </div>

        {/* Right-aligned Search Bar & Dark Mode Toggle */}
        <div className="flex items-center gap-4 ml-auto mr-2">
          <div className="hidden md:flex w-[280px] relative group">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#9CA3AF] group-focus-within:text-[#00D09C] transition-colors" size={16} />
            <input 
              type="text" 
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search mutual funds..." 
              className="w-full bg-[#F3F4F6] dark:bg-[#1F2937] hover:bg-[#E5E7EB] dark:hover:bg-[#374151] text-[#111827] dark:text-[#F3F4F6] placeholder-[#9CA3AF] rounded-xl pl-10 pr-4 py-2 text-[13px] focus:outline-none focus:ring-2 focus:ring-[#00D09C]/30 transition-all border border-transparent focus:bg-white dark:focus:bg-[#111827] focus:border-[#00D09C]"
            />
          </div>
          <button 
            onClick={() => setIsDarkMode(!isDarkMode)} 
            className="p-2 text-[#6B7280] dark:text-[#9CA3AF] hover:bg-[#F3F4F6] dark:hover:bg-[#1F2937] rounded-full transition-colors"
            title="Toggle Dark Mode"
          >
            {isDarkMode ? <Sun size={20} /> : <Moon size={20} />}
          </button>
        </div>

        <div className="hidden">
          <div className="flex items-center gap-2.5 px-3 py-1.5 bg-[#F0FDF4] rounded-full border border-[#bbf7d0]/50 shadow-sm">
            <div className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#22C55E] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#16A34A]"></span>
            </div>
            <span className="text-[12px] font-semibold text-[#166534] hidden sm:block tracking-wide">System Online</span>
          </div>
          <div className="w-10 h-10 rounded-full bg-[#F3F4F6] border border-[#E5E7EB] flex items-center justify-center text-[#6B7280] hover:bg-[#E5E7EB] hover:text-[#374151] cursor-pointer transition-colors shadow-sm">
            <User size={18} />
          </div>
        </div>
      </header>

      {/* Main Layout Area */}
      <div className="flex flex-1 overflow-hidden relative">
        
        {/* Sidebar */}
        <AnimatePresence>
          {(isSidebarOpen || window.innerWidth >= 768) && (
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", bounce: 0, duration: 0.3 }}
              className="absolute md:relative z-10 w-[280px] min-w-[280px] bg-[#F2FCF9] dark:bg-[#0B0F19] border-r border-[#00D09C]/15 dark:border-[#1F2937] h-full flex flex-col shadow-[4px_0_24px_rgba(0,0,0,0.05)] md:shadow-none transition-colors"
            >
              <div className="p-4 border-b border-[#00D09C]/10 dark:border-[#1F2937]">
                <button 
                  onClick={handleNewConversation}
                  className="w-full flex items-center justify-center gap-2 bg-[#00D09C] hover:bg-[#00B88A] text-white font-semibold py-2.5 px-4 rounded-xl shadow-[0_4px_12px_rgba(0,208,156,0.2)] transition-all"
                >
                  <Plus size={18} />
                  <span>New Chat</span>
                </button>
              </div>

              <div className="flex flex-col flex-1 overflow-hidden p-4 gap-4 bg-transparent min-h-0">
                
                {/* Dynamic Tabs Card */}
                <div className="flex flex-col shrink-0 max-h-[35vh] bg-white dark:bg-[#111827] rounded-2xl shadow-[0_4px_12px_rgba(0,208,156,0.04)] border border-[#00D09C]/15 dark:border-[#1F2937] overflow-hidden transition-colors">
                  <div className="px-3 py-2 border-b border-[#00D09C]/10 dark:border-[#1F2937] bg-white dark:bg-[#111827] flex gap-1 shrink-0">
                     <button onClick={() => setActiveTab('recent')} className={`flex-1 flex justify-center items-center gap-1.5 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-lg transition-colors ${activeTab === 'recent' ? 'bg-[#F0FDF4] dark:bg-[#1F2937] text-[#00D09C]' : 'text-[#9CA3AF] hover:text-[#4B5563] dark:hover:text-[#D1D5DB]'}`}>
                        <MessageSquare size={13} /> Recent
                     </button>
                     <button onClick={() => setActiveTab('saved')} className={`flex-1 flex justify-center items-center gap-1.5 py-1.5 text-[11px] font-bold uppercase tracking-wider rounded-lg transition-colors ${activeTab === 'saved' ? 'bg-[#F0FDF4] dark:bg-[#1F2937] text-[#00D09C]' : 'text-[#9CA3AF] hover:text-[#4B5563] dark:hover:text-[#D1D5DB]'}`}>
                        <BookmarkPlus size={13} /> Saved
                     </button>
                  </div>
                  <div className="flex-1 overflow-y-auto custom-scrollbar p-2 snap-y snap-mandatory bg-white dark:bg-[#111827]">
                    {activeTab === 'recent' ? (
                      <div className="space-y-1">
                        {displayChats.map((chatTitle, idx) => {
                          const isActive = chatTitle === activeChatTitle;
                          return (
                            <button 
                              key={idx}
                              onClick={() => {
                                if (!isActive) {
                                  handleNewConversation();
                                  setTimeout(() => handleSend(chatTitle), 50);
                                }
                              }}
                              className={`w-full text-left truncate text-[13px] py-2 px-3 rounded-xl transition-colors relative overflow-hidden group snap-start scroll-m-2 ${
                                isActive 
                                  ? 'text-[#00D09C] font-semibold bg-[#F0FDF4] dark:bg-[#1F2937]' 
                                  : 'text-[#4B5563] dark:text-[#D1D5DB] hover:bg-[#F2FCF9] dark:hover:bg-[#1F2937] font-medium'
                              }`}
                            >
                              <div className={`absolute left-0 top-1/2 -translate-y-1/2 w-[3px] rounded-r-full transition-all ${
                                isActive ? 'h-4 bg-[#00D09C]' : 'h-0 bg-[#00D09C] group-hover:h-3'
                              }`}></div>
                              {chatTitle}
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="space-y-1">
                        {savedItems.length > 0 ? savedItems.map((item, idx) => (
                          <div key={idx} className="flex justify-between items-center group w-full text-left text-[13px] py-2 px-3 rounded-xl hover:bg-[#F2FCF9] dark:hover:bg-[#1F2937] transition-colors snap-start scroll-m-2 font-medium text-[#4B5563] dark:text-[#D1D5DB]">
                            <span className="truncate pr-2 cursor-pointer" onClick={() => { handleNewConversation(); setTimeout(() => handleSend(item.content), 50); }}>{item.content}</span>
                            <button onClick={() => toggleSaveItem(item)} className="text-[#9CA3AF] hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                              <Trash2 size={14}/>
                            </button>
                          </div>
                        )) : (
                          <div className="px-3 py-4 text-[12px] text-center text-[#9CA3AF]">No saved messages yet.</div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Supported Funds Card */}
                <div className="flex flex-col flex-1 bg-white dark:bg-[#111827] rounded-2xl shadow-[0_4px_12px_rgba(0,208,156,0.04)] border border-[#00D09C]/15 dark:border-[#1F2937] overflow-hidden min-h-0 transition-colors">
                  <div className="px-4 py-3 border-b border-[#00D09C]/10 dark:border-[#1F2937] bg-white dark:bg-[#111827] flex items-center gap-2 shrink-0">
                    <PieChart size={14} className="text-[#00D09C]" />
                    <h2 className="text-[11px] font-bold text-[#4B5563] dark:text-[#9CA3AF] uppercase tracking-wider">Supported Funds</h2>
                  </div>
                  <div className="flex-1 overflow-y-auto custom-scrollbar p-2 snap-y snap-mandatory bg-white dark:bg-[#111827]">
                    <div className="space-y-1">
                      {filteredFunds.length > 0 ? (
                        filteredFunds.map((fund, idx) => (
                          <button key={idx} onClick={() => handleSend(`Tell me about ${fund}`)} className="w-full text-left truncate text-[#4B5563] dark:text-[#D1D5DB] text-[13px] py-2 px-3 rounded-xl hover:bg-[#F2FCF9] dark:hover:bg-[#1F2937] transition-colors snap-start scroll-m-2 font-medium">
                            {fund}
                          </button>
                        ))
                      ) : (
                        <div className="px-3 py-2 text-[13px] text-[#9CA3AF]">No funds found.</div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        {/* Mobile Sidebar Overlay */}
        {isSidebarOpen && (
          <div 
            className="md:hidden fixed inset-0 bg-[#111827]/20 backdrop-blur-sm z-0"
            onClick={() => setIsSidebarOpen(false)}
          ></div>
        )}

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col lg:flex-row h-full bg-gradient-to-br from-[#E6F8F3]/60 dark:from-[#00D09C]/10 via-[#F7F8FA] dark:via-[#0B0F19] to-[#F7F8FA] dark:to-[#0B0F19] relative transition-colors overflow-hidden">
          
          {/* Left Pane: Fund Carousel (Phase 3 Placeholder) */}
          <div className="hidden lg:flex flex-col w-full lg:w-[60%] border-r border-[#E5E7EB] dark:border-[#1F2937] p-8 items-center justify-center bg-white/40 dark:bg-[#0B0F19]/40 backdrop-blur-md relative overflow-hidden">
             <FundCarousel 
               fundsList={supportedFunds} 
               onFundClick={(fundName) => {
                 handleSend(`Give me a detailed analysis of ${fundName}`);
               }} 
             />
          </div>

          {/* Right Pane: Chatbot */}
          <div className="w-full lg:w-[40%] flex flex-col h-full bg-white/60 dark:bg-[#111827]/60 backdrop-blur-sm relative shadow-[-10px_0_30px_rgba(0,0,0,0.02)]">
            {/* Chat Messages */}
            <div id="chat-scroll-container" className="flex-1 overflow-y-auto px-4 md:px-6 py-6 pb-6 custom-scrollbar">
              <div className="max-w-[900px] mx-auto flex flex-col gap-6">
              
              <AnimatePresence mode="popLayout">
                {messages.length === 0 ? (
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.95, filter: 'blur(4px)' }}
                    animate={{ opacity: 1, scale: 1, filter: 'blur(0px)' }}
                    exit={{ opacity: 0, scale: 0.95, filter: 'blur(4px)' }}
                    transition={{ duration: 0.4, ease: "easeOut" }}
                    className="flex flex-col items-center justify-center pt-2 md:pt-6 pb-8 text-center"
                  >
                    <div className="relative mb-5">
                      <div className="absolute inset-0 bg-[#00D09C] opacity-20 blur-2xl rounded-full scale-150"></div>
                      <div className="w-16 h-16 bg-white dark:bg-[#111827] rounded-2xl shadow-[0_4px_20px_rgba(0,208,156,0.15)] flex items-center justify-center relative overflow-hidden border border-[#00D09C]/20">
                        <img src="/groww-logo.png" alt="Groww Logo" className="w-10 h-10 object-contain" />
                      </div>
                    </div>
                    <h2 className="text-[24px] md:text-[30px] font-bold text-[#111827] dark:text-[#F3F4F6] mb-2 tracking-tight">How can I help you today?</h2>
                    <p className="text-[#6B7280] dark:text-[#9CA3AF] text-[15px] max-w-md mb-6 leading-relaxed px-4">
                      Ask anything about mutual funds. I provide factual, source-backed answers directly from AMCs.
                    </p>
                    
                    <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-3xl">
                      {exampleChips.map((chip, idx) => (
                        <motion.button
                          key={idx}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: idx * 0.1 + 0.1 }}
                          onClick={() => handleSend(chip)}
                          className="text-left p-4 bg-white dark:bg-[#111827] hover:bg-[#F2FCF9] dark:hover:bg-[#1F2937] border border-[#00D09C]/20 dark:border-[#1F2937] rounded-xl shadow-[0_2px_8px_rgba(0,208,156,0.06)] hover:border-[#00D09C]/60 hover:shadow-[0_4px_16px_rgba(0,208,156,0.12)] transition-all flex flex-col justify-between group h-full"
                        >
                          <span className="text-[#374151] dark:text-[#D1D5DB] font-medium leading-snug mb-3 text-[14px]">{chip}</span>
                          <div className="w-7 h-7 rounded-full bg-[#F3F4F6] dark:bg-[#374151] group-hover:bg-[#00D09C] group-hover:text-white flex items-center justify-center text-[#9CA3AF] dark:text-[#D1D5DB] transition-colors self-end shadow-sm">
                            <Send size={13} className="ml-0.5" />
                          </div>
                        </motion.button>
                      ))}
                    </div>
                  </motion.div>
                ) : (
                  messages.map((msg, index) => (
                    <motion.div 
                      key={msg.id}
                      initial={{ opacity: 0, y: 15, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{ duration: 0.3, type: "spring", stiffness: 250, damping: 25 }}
                      className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      {msg.role === 'user' ? (
                        <div className="max-w-[85%] md:max-w-[75%] bg-[#00D09C] text-white px-5 py-3.5 rounded-[24px] rounded-tr-[6px] shadow-[0_4px_12px_rgba(0,208,156,0.15)]">
                          <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                          <div className="text-[10px] text-white/70 mt-1.5 font-medium tracking-wide flex justify-end">
                            {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </div>
                        </div>
                      ) : msg.role === 'refusal' ? (
                        <div className="max-w-[85%] md:max-w-[80%] bg-[#FFFBEB] border border-[#FCD34D] text-[#92400E] px-5 py-4 rounded-[24px] rounded-tl-[6px] shadow-[0_4px_16px_rgba(0,0,0,0.04)] flex gap-3">
                          <Info size={20} className="shrink-0 mt-0.5 text-[#D97706]" />
                          <div>
                            <p className="text-[15px] leading-relaxed font-medium">{msg.content}</p>
                          </div>
                        </div>
                      ) : (
                        <div className="flex gap-4 max-w-[85%] md:max-w-[80%]">
                          <div className="w-8 h-8 rounded-full bg-white border border-[#E5E7EB] shadow-sm flex items-center justify-center shrink-0 mt-1 hidden sm:flex">
                            <img src="/groww-logo.png" alt="Bot" className="w-5 h-5 object-contain" />
                          </div>
                          <div className="bg-white dark:bg-[#111827] border border-[#E5E7EB] dark:border-[#1F2937] p-5 rounded-[24px] rounded-tl-[6px] shadow-[0_4px_20px_rgba(0,0,0,0.03)] hover:shadow-[0_8px_30px_rgba(0,0,0,0.06)] transition-all group relative">
                            {(() => {
                              const parsed = parseMessageContent(msg.content);
                              return (
                                <>
                                  <p className="text-[15px] text-[#374151] dark:text-[#D1D5DB] leading-relaxed whitespace-pre-wrap pr-6">{parsed.text}</p>
                                  
                                  <button 
                                    onClick={() => toggleSaveItem(msg)} 
                                    className={`absolute top-4 right-4 p-1.5 rounded-full transition-all ${savedItems.some(i => i.id === msg.id) ? 'bg-[#00D09C]/10 text-[#00D09C]' : 'text-[#9CA3AF] opacity-0 group-hover:opacity-100 hover:bg-[#F3F4F6] dark:hover:bg-[#374151]'}`}
                                    title={savedItems.some(i => i.id === msg.id) ? "Saved" : "Save for Later"}
                                  >
                                    <BookmarkPlus size={16} />
                                  </button>

                                  {/* Render Interactive Chart if available */}
                                  {parsed.chartData && parsed.chartData.labels && (
                                    <div className="mt-5 p-4 bg-[#F9FAFB] dark:bg-[#1F2937] rounded-xl border border-[#E5E7EB] dark:border-[#374151]">
                                      <div className="h-[200px] w-full">
                                        <ResponsiveContainer width="100%" height="100%">
                                          {parsed.chartData.type === 'bar' ? (
                                            <BarChart data={parsed.chartData.labels.map((l: string, i: number) => ({ name: l, value: parsed.chartData.datasets[0].data[i] }))}>
                                              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                                              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#9CA3AF', fontSize: 12}} />
                                              <RechartsTooltip cursor={{fill: 'rgba(0,208,156,0.05)'}} contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}} />
                                              <Bar dataKey="value" fill="#00D09C" radius={[4, 4, 0, 0]} barSize={30} />
                                            </BarChart>
                                          ) : (
                                            <LineChart data={parsed.chartData.labels.map((l: string, i: number) => ({ name: l, value: parsed.chartData.datasets[0].data[i] }))}>
                                              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                                              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#9CA3AF', fontSize: 12}} />
                                              <RechartsTooltip contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}} />
                                              <Line type="monotone" dataKey="value" stroke="#00D09C" strokeWidth={3} dot={{r: 4, fill: '#00D09C', strokeWidth: 2, stroke: '#fff'}} activeDot={{r: 6}} />
                                            </LineChart>
                                          )}
                                        </ResponsiveContainer>
                                      </div>
                                    </div>
                                  )}

                                  {/* Source Citation */}
                                  {(msg.sourceLink || msg.sourceDate) && (
                                    <div className="mt-5 pt-4 border-t border-[#F3F4F6] dark:border-[#1F2937] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                                      {msg.sourceLink && (
                                        <a 
                                          href={msg.sourceLink} 
                                          target="_blank" 
                                          rel="noreferrer" 
                                          className="inline-flex items-center gap-2 px-3 py-2 bg-[#F9FAFB] dark:bg-[#1F2937] hover:bg-white dark:hover:bg-[#374151] border border-[#E5E7EB] dark:border-[#374151] hover:border-[#00D09C] dark:hover:border-[#00D09C] hover:shadow-[0_2px_8px_rgba(0,208,156,0.1)] rounded-xl text-[12px] text-[#4B5563] dark:text-[#D1D5DB] font-medium transition-all group max-w-full"
                                        >
                                          <div className="w-5 h-5 rounded bg-white dark:bg-[#111827] border border-[#E5E7EB] dark:border-[#374151] flex items-center justify-center text-[#9CA3AF] group-hover:border-[#00D09C]/30 group-hover:text-[#00D09C] transition-colors shrink-0">
                                            <ExternalLink size={12} />
                                          </div>
                                          <span className="truncate group-hover:text-[#111827] dark:group-hover:text-[#F3F4F6]">{msg.sourceLink.replace('https://', '').replace('www.', '')}</span>
                                        </a>
                                      )}
                                      {msg.sourceDate && (
                                        <span className="text-[11px] text-[#9CA3AF] font-medium px-1 uppercase tracking-wider">{msg.sourceDate}</span>
                                      )}
                                      <div className="flex items-center gap-2 ml-auto">
                                        <button 
                                          onClick={() => handleFeedback(msg.id, 1)}
                                          disabled={!!submittedFeedback[msg.id]}
                                          className={`p-1.5 rounded-full transition-colors ${submittedFeedback[msg.id] === 1 ? 'text-[#00D09C] bg-[#00D09C]/10' : 'text-[#9CA3AF] hover:text-[#00D09C] hover:bg-[#F3F4F6] dark:hover:bg-[#374151]'}`}
                                          title="Helpful"
                                        >
                                          <ThumbsUp size={14} />
                                        </button>
                                        <button 
                                          onClick={() => handleFeedback(msg.id, -1)}
                                          disabled={!!submittedFeedback[msg.id]}
                                          className={`p-1.5 rounded-full transition-colors ${submittedFeedback[msg.id] === -1 ? 'text-red-500 bg-red-500/10' : 'text-[#9CA3AF] hover:text-red-500 hover:bg-[#F3F4F6] dark:hover:bg-[#374151]'}`}
                                          title="Not Helpful"
                                        >
                                          <ThumbsDown size={14} />
                                        </button>
                                      </div>
                                    </div>
                                  )}
                                  
                                  {/* Follow Up Chips */}
                                  {index === messages.length - 1 && parsed.followUps && parsed.followUps.length > 0 && !isTyping && (
                                    <div className="mt-5 flex flex-wrap gap-2 animate-in fade-in slide-in-from-bottom-2 duration-500">
                                      {parsed.followUps.map((q: string, i: number) => (
                                        <button 
                                          key={i} 
                                          onClick={() => handleSend(q)}
                                          className="px-3.5 py-2 bg-[#E6F8F3] dark:bg-[#00D09C]/10 text-[#00D09C] border border-[#00D09C]/20 hover:border-[#00D09C]/60 rounded-xl text-[13px] font-medium hover:bg-[#00D09C] hover:text-white transition-all shadow-sm text-left leading-tight max-w-full"
                                        >
                                          {q}
                                        </button>
                                      ))}
                                    </div>
                                  )}
                                </>
                              );
                            })()}
                          </div>
                        </div>
                      )}
                    </motion.div>
                  ))
                )}

                {/* Typing Indicator */}
                {isTyping && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex justify-start w-full gap-4 max-w-[85%] md:max-w-[80%]"
                  >
                    <div className="w-8 h-8 rounded-full bg-white border border-[#E5E7EB] shadow-sm flex items-center justify-center shrink-0 mt-1 hidden sm:flex">
                      <img src="/groww-logo.png" alt="Bot" className="w-5 h-5 object-contain" />
                    </div>
                    <div className="bg-white dark:bg-[#111827] border border-[#E5E7EB] dark:border-[#1F2937] px-5 py-4 rounded-[24px] rounded-tl-[6px] shadow-[0_4px_20px_rgba(0,0,0,0.03)] flex flex-col gap-2 min-w-[200px]">
                       <div className="h-4 bg-[#F3F4F6] dark:bg-[#374151] rounded-md w-3/4 animate-pulse"></div>
                       <div className="h-4 bg-[#F3F4F6] dark:bg-[#374151] rounded-md w-1/2 animate-pulse"></div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
              <div ref={messagesEndRef} className="h-4" />
            </div>
          </div>

          {/* Input Area Footer */}
          <div className="shrink-0 bg-transparent pt-4 pb-4 px-4 md:px-6 z-10 relative">
            <div className="max-w-[900px] mx-auto flex flex-col items-center w-full">
              <div className="relative group flex w-full shadow-[0_4px_20px_rgba(0,208,156,0.1)] rounded-2xl bg-white dark:bg-[#1F2937] border-2 border-[#00D09C]/60 hover:border-[#00D09C] hover:shadow-[0_4px_24px_rgba(0,208,156,0.2)] focus-within:border-[#00D09C] focus-within:ring-4 focus-within:ring-[#00D09C]/20 focus-within:shadow-[0_8px_30px_rgba(0,208,156,0.25)] transition-all duration-300 p-1.5 pl-5">
                <input 
                  type="text" 
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask a question about mutual funds..."
                  className="w-full bg-transparent text-[#111827] dark:text-[#F3F4F6] placeholder-[#9CA3AF] py-3 focus:outline-none text-[15px] pr-4"
                  disabled={isTyping}
                />
                <div className="flex gap-1.5 shrink-0 items-center">
                  {SpeechRecognition && (
                    <button 
                      onClick={toggleListening}
                      disabled={isTyping}
                      className={`w-10 h-10 flex items-center justify-center rounded-xl transition-all ${isListening ? 'bg-red-100 dark:bg-red-900/30 text-red-500 animate-pulse' : 'text-[#9CA3AF] hover:bg-[#F3F4F6] dark:hover:bg-[#374151] hover:text-[#4B5563] dark:hover:text-[#D1D5DB]'}`}
                      title={isListening ? "Listening..." : "Voice Input"}
                    >
                      <Mic size={18} />
                    </button>
                  )}
                  <button 
                    onClick={() => handleSend(input)}
                    disabled={!input.trim() || isTyping}
                    className="w-12 h-12 flex items-center justify-center rounded-xl bg-[#00D09C] hover:bg-[#00B88A] text-white disabled:bg-[#E5E7EB] dark:disabled:bg-[#374151] disabled:text-[#9CA3AF] dark:disabled:text-[#6B7280] transition-all disabled:shadow-none shrink-0"
                  >
                    {isTyping ? <Loader2 size={20} className="animate-spin" /> : <Send size={18} className={input.trim() ? 'ml-0.5' : ''} />}
                  </button>
                </div>
              </div>
              <div className="text-[10px] font-semibold text-[#9CA3AF] mt-2.5 flex items-center tracking-widest uppercase">
                Powered by RAG
              </div>
            </div>
          </div>
          </div>

        </main>
      </div>
    </div>
  );
}
