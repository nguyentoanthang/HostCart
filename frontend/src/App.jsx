import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  Gamepad2,
  Film,
  Tv,
  BookOpen,
  BarChart3,
  LayoutDashboard,
  DownloadCloud,
  Settings as SettingsIcon,
  Plus,
  Search,
  Trash2,
  Edit3,
  Star,
  CheckCircle2,
  Clock,
  LogOut,
  User as UserIcon,
  ExternalLink,
  Sparkles,
  RefreshCw,
  SlidersHorizontal,
  Bookmark,
  TrendingUp,
  X,
  Upload,
  Check,
  ChevronRight,
  Shield,
  Layers,
  Flame
} from "lucide-react";
import { auth, collection, search, importExport, settings, getToken } from "./api";
import StatisticsView from "./components/StatisticsView";

const TYPE_CONFIG = {
  all: { label: "All Media", icon: "⚡", LucideIcon: LayoutDashboard, color: "text-red-400", bg: "bg-red-500/20 text-red-300", bar: "bg-red-500" },
  game: { label: "Video Games", icon: "🎮", LucideIcon: Gamepad2, color: "text-red-400", bg: "bg-red-500/20 text-red-300", bar: "bg-red-500" },
  movie: { label: "Movies", icon: "🎬", LucideIcon: Film, color: "text-amber-400", bg: "bg-amber-500/20 text-amber-300", bar: "bg-amber-400" },
  tv_show: { label: "TV Shows", icon: "📺", LucideIcon: Tv, color: "text-cyan-400", bg: "bg-cyan-500/20 text-cyan-300", bar: "bg-cyan-400" },
  book: { label: "Books", icon: "📚", LucideIcon: BookOpen, color: "text-emerald-400", bg: "bg-emerald-500/20 text-emerald-300", bar: "bg-emerald-400" },
};

const DEMO_SEED_ITEMS = [
  {
    media: {
      media_type: "game",
      title: "Marvel's Spider-Man",
      original_title: "Marvel's Spider-Man Remastered",
      release_year: 2022,
      poster_url: "https://images.unsplash.com/photo-1608889175123-8ee362201f81?auto=format&fit=crop&w=600&q=80",
      backdrop_url: "https://images.unsplash.com/photo-1608889175123-8ee362201f81?auto=format&fit=crop&w=1200&q=80",
      summary: "In Marvel's Spider-Man Remastered, the worlds of Peter Parker and Spider-Man collide in an original action-packed story.",
      genres: ["Action", "Adventure", "Open World"],
      creators: ["Insomniac Games"],
      external_id: "demo-igdb-1",
      external_source: "igdb"
    },
    status: "in_progress",
    rating: 9.4,
    is_favorite: true,
    playtime_hours: 34.5,
    tags: ["Steam", "PC"]
  },
  {
    media: {
      media_type: "movie",
      title: "Dune: Part Two",
      release_year: 2024,
      poster_url: "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=600&q=80",
      backdrop_url: "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=1200&q=80",
      summary: "Paul Atreides unites with Chani and the Fremen while seeking revenge against the conspirators who destroyed his family.",
      genres: ["Sci-Fi", "Epic", "Adventure"],
      creators: ["Denis Villeneuve"],
      runtime_minutes: 166,
      external_id: "demo-tmdb-1",
      external_source: "tmdb"
    },
    status: "completed",
    rating: 9.6,
    is_favorite: true,
    rewatch_count: 2,
    tags: ["4K Blu-ray", "Masterpiece"]
  },
  {
    media: {
      media_type: "tv_show",
      title: "Arcane: League of Legends",
      release_year: 2024,
      poster_url: "https://images.unsplash.com/photo-1579783900882-c0d3dad7b119?auto=format&fit=crop&w=600&q=80",
      backdrop_url: "https://images.unsplash.com/photo-1579783900882-c0d3dad7b119?auto=format&fit=crop&w=1200&q=80",
      summary: "Amid the stark discord of twin cities Piltover and Zaun, two sisters fight on rival sides of a war between magic technologies.",
      genres: ["Animation", "Sci-Fi", "Action"],
      creators: ["Fortiche", "Riot"],
      total_episodes: 18,
      external_id: "demo-tmdb-2",
      external_source: "tmdb"
    },
    status: "in_progress",
    rating: 9.5,
    is_favorite: true,
    current_episode: 15,
    tags: ["Netflix", "Animation"]
  },
  {
    media: {
      media_type: "book",
      title: "Project Hail Mary",
      release_year: 2021,
      poster_url: "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=600&q=80",
      backdrop_url: "https://images.unsplash.com/photo-1451187580459-43490279c0fa?auto=format&fit=crop&w=1200&q=80",
      summary: "Ryland Grace is the sole survivor on a desperate, last-chance mission—and if he fails, humanity itself will perish.",
      genres: ["Sci-Fi", "Hard Sci-Fi"],
      creators: ["Andy Weir"],
      total_pages: 476,
      external_id: "demo-ol-1",
      external_source: "openlibrary"
    },
    status: "in_progress",
    rating: 9.3,
    is_favorite: true,
    current_page: 312,
    tags: ["Hardcover", "Sci-Fi"]
  },
  {
    media: {
      media_type: "game",
      title: "Elden Ring: Shadow of the Erdtree",
      release_year: 2024,
      poster_url: "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=600&q=80",
      backdrop_url: "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=1200&q=80",
      summary: "Guided by Empyrean Miquella, players are beckoned to the Land of Shadow, a place obscured by the Erdtree.",
      genres: ["Action RPG", "Dark Fantasy"],
      creators: ["FromSoftware"],
      external_id: "demo-igdb-2",
      external_source: "igdb"
    },
    status: "completed",
    rating: 9.8,
    is_favorite: true,
    playtime_hours: 105.0,
    tags: ["Steam", "GotY"]
  },
  {
    media: {
      media_type: "game",
      title: "Black Myth: Wukong",
      release_year: 2024,
      poster_url: "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=600&q=80",
      backdrop_url: "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=1200&q=80",
      summary: "An action RPG rooted in Chinese mythology where you set forth as the Destined One.",
      genres: ["Action RPG", "Mythology"],
      creators: ["Game Science"],
      external_id: "demo-igdb-3",
      external_source: "igdb"
    },
    status: "plan_to",
    rating: 9.1,
    playtime_hours: 4.0,
    tags: ["Steam", "Backlog"]
  },
  {
    media: {
      media_type: "movie",
      title: "Oppenheimer",
      release_year: 2023,
      poster_url: "https://images.unsplash.com/photo-1440404653325-ab127d49abc1?auto=format&fit=crop&w=600&q=80",
      backdrop_url: "https://images.unsplash.com/photo-1440404653325-ab127d49abc1?auto=format&fit=crop&w=1200&q=80",
      summary: "The story of American scientist J. Robert Oppenheimer and his role in the development of the atomic bomb.",
      genres: ["Biography", "Drama"],
      creators: ["Christopher Nolan"],
      runtime_minutes: 180,
      external_id: "demo-tmdb-3",
      external_source: "tmdb"
    },
    status: "completed",
    rating: 9.4,
    rewatch_count: 1,
    tags: ["4K UHD", "Biography"]
  },
  {
    media: {
      media_type: "tv_show",
      title: "Shōgun",
      release_year: 2024,
      poster_url: "https://images.unsplash.com/photo-1528164344705-475426879c0d?auto=format&fit=crop&w=600&q=80",
      backdrop_url: "https://images.unsplash.com/photo-1528164344705-475426879c0d?auto=format&fit=crop&w=1200&q=80",
      summary: "Lord Yoshii Toranaga fights for his life as his enemies on the Council of Regents unite against him.",
      genres: ["Historical Drama", "War"],
      creators: ["FX Networks"],
      total_episodes: 10,
      external_id: "demo-tmdb-4",
      external_source: "tmdb"
    },
    status: "completed",
    rating: 9.6,
    current_episode: 10,
    tags: ["Streaming", "Emmy"]
  },
  {
    media: {
      media_type: "book",
      title: "The Three-Body Problem",
      release_year: 2014,
      poster_url: "https://images.unsplash.com/photo-1532012197267-da84d127e765?auto=format&fit=crop&w=600&q=80",
      backdrop_url: "https://images.unsplash.com/photo-1532012197267-da84d127e765?auto=format&fit=crop&w=1200&q=80",
      summary: "Set against the backdrop of China's Cultural Revolution, a secret military project sends signals into space.",
      genres: ["Sci-Fi", "Hard Sci-Fi"],
      creators: ["Cixin Liu"],
      total_pages: 390,
      external_id: "demo-ol-2",
      external_source: "openlibrary"
    },
    status: "completed",
    rating: 8.9,
    current_page: 390,
    tags: ["Kindle", "Hugo Winner"]
  },
  {
    media: {
      media_type: "movie",
      title: "Blade Runner 2049",
      release_year: 2017,
      poster_url: "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=600&q=80",
      backdrop_url: "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=1200&q=80",
      summary: "Young Blade Runner K's discovery of a long-buried secret leads him to track down former Blade Runner Rick Deckard.",
      genres: ["Sci-Fi", "Neo-Noir"],
      creators: ["Denis Villeneuve"],
      runtime_minutes: 164,
      external_id: "demo-tmdb-5",
      external_source: "tmdb"
    },
    status: "wishlist",
    rating: 9.2,
    tags: ["Digital", "Wishlist"]
  }
];

export default function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeNav, setActiveNav] = useState("all");
  const [activeTab, setActiveTab] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [heroIndex, setHeroIndex] = useState(0);

  // Modals & Forms
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState("login");
  const [authUsername, setAuthUsername] = useState("");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authError, setAuthError] = useState("");
  const [authSubmitting, setAuthSubmitting] = useState(false);

  // Add Media Modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [addTab, setAddTab] = useState("search");
  const [searchType, setSearchType] = useState("game");
  const [searchQueryTerm, setSearchQueryTerm] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState("");

  // Manual Add Form State
  const [manualTitle, setManualTitle] = useState("");
  const [manualType, setManualType] = useState("game");
  const [manualCreator, setManualCreator] = useState("");
  const [manualYear, setManualYear] = useState(new Date().getFullYear());
  const [manualPoster, setManualPoster] = useState("");
  const [manualStatus, setManualStatus] = useState("in_progress");
  const [manualRating, setManualRating] = useState(9.0);
  const [manualTotalMetric, setManualTotalMetric] = useState(40);
  const [manualGenres, setManualGenres] = useState("Action, Adventure");
  const [manualOverview, setManualOverview] = useState("");

  // Edit / Detail Modal
  const [selectedItem, setSelectedItem] = useState(null);
  const [editForm, setEditForm] = useState(null);

  // Settings State
  const [runtimeSettings, setRuntimeSettings] = useState(null);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState("");

  // Toast Notification
  const [toast, setToast] = useState(null);

  const showToast = (message, type = "success") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  // Check auth and load user + collection
  const loadUserDataAndCollection = useCallback(async () => {
    setLoading(true);
    const token = getToken();
    if (token) {
      try {
        const user = await auth.getMe();
        setCurrentUser(user);
        const col = await collection.list();
        setItems(col);
      } catch (err) {
        console.warn("Auth check failed:", err);
        auth.logout();
        setCurrentUser(null);
        setItems([]);
      }
    } else {
      setCurrentUser(null);
      setItems([]);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadUserDataAndCollection();
  }, [loadUserDataAndCollection]);

  // Load settings when settings nav is activated
  useEffect(() => {
    if (activeNav === "settings" && currentUser?.is_admin) {
      setSettingsLoading(true);
      settings.getSettings()
        .then(data => setRuntimeSettings(data))
        .catch(err => showToast(`Failed to load settings: ${err.message}`, "error"))
        .finally(() => setSettingsLoading(false));
    }
  }, [activeNav, currentUser]);

  // Auth Submit
  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError("");
    setAuthSubmitting(true);
    try {
      if (authMode === "login") {
        await auth.login(authUsername, authPassword);
      } else {
        await auth.register(authUsername, authEmail || `${authUsername}@example.com`, authPassword);
      }
      setShowAuthModal(false);
      setAuthUsername("");
      setAuthPassword("");
      setAuthEmail("");
      showToast(authMode === "login" ? "Logged in successfully!" : "Account created & logged in!");
      await loadUserDataAndCollection();
    } catch (err) {
      setAuthError(err.message || "Authentication failed. Check credentials.");
    } finally {
      setAuthSubmitting(false);
    }
  };

  const handleLogout = () => {
    auth.logout();
    setCurrentUser(null);
    setItems([]);
    showToast("Signed out.");
  };

  // Seed Demo Collection
  const handleSeedDemo = async () => {
    try {
      let activeUser = currentUser;
      if (!activeUser) {
        // Auto register or login as demo admin
        try {
          await auth.register("curator_admin", "admin@hostcart.local", "HostCart2026!");
        } catch {
          await auth.login("curator_admin", "HostCart2026!");
        }
        activeUser = await auth.getMe();
        setCurrentUser(activeUser);
      }

      showToast("Seeding 10 high-quality media items across all categories...", "info");
      for (const item of DEMO_SEED_ITEMS) {
        try {
          await collection.create(item);
        } catch (e) {
          console.log("Item exists or skipped:", e.message);
        }
      }
      const updated = await collection.list();
      setItems(updated);
      showToast("Demo collection seeded successfully! 10 items added.");
    } catch (err) {
      showToast(`Seed failed: ${err.message}`, "error");
    }
  };

  // Quick increment progress
  const handleQuickIncrement = async (id, e) => {
    if (e) e.stopPropagation();
    try {
      const entry = items.find(i => i.id === id);
      if (!entry) return;

      const mediaType = entry.media?.media_type || "game";
      const step = mediaType === "book" ? 25 : mediaType === "game" ? 2 : 1;

      // Optimistic update
      setItems(prev => prev.map(item => {
        if (item.id !== id) return item;
        const mt = item.media?.media_type;
        let newPlaytime = item.playtime_hours;
        let newEp = item.current_episode;
        let newPage = item.current_page;
        let newRewatch = item.rewatch_count;
        let newStatus = item.status === "plan_to" ? "in_progress" : item.status;

        if (mt === "game") newPlaytime += step;
        else if (mt === "movie") newRewatch += step;
        else if (mt === "tv_show") {
          newEp += step;
          if (item.media?.total_episodes && newEp >= item.media.total_episodes) newStatus = "completed";
        } else if (mt === "book") {
          newPage += step;
          if (item.media?.total_pages && newPage >= item.media.total_pages) newStatus = "completed";
        }

        return {
          ...item,
          status: newStatus,
          playtime_hours: newPlaytime,
          current_episode: newEp,
          current_page: newPage,
          rewatch_count: newRewatch
        };
      }));

      // Call live backend
      const updated = await collection.increment(id, step);
      setItems(prev => prev.map(i => i.id === id ? updated : i));
      showToast(`Logged progress for "${entry.media?.title}" (+${step})`);
    } catch (err) {
      showToast(`Increment error: ${err.message}`, "error");
      // Reload on failure
      const refreshed = await collection.list();
      setItems(refreshed);
    }
  };

  // Search External Providers
  const handleExternalSearch = async (e) => {
    if (e) e.preventDefault();
    if (!searchQueryTerm.trim()) return;
    setIsSearching(true);
    setSearchError("");
    try {
      const results = await search.searchExternal(searchQueryTerm, searchType);
      setSearchResults(results || []);
      if (!results || results.length === 0) {
        setSearchError("No results found. Try another query or switch provider.");
      }
    } catch (err) {
      setSearchError(`Search failed: ${err.message}`);
    } finally {
      setIsSearching(false);
    }
  };

  // Add from External Search Result
  const handleAddSearchResult = async (res) => {
    try {
      const payload = {
        media: res,
        status: "in_progress",
        rating: 9.0,
        is_favorite: false,
        playtime_hours: res.media_type === "game" ? 1.0 : 0.0,
        current_episode: res.media_type === "tv_show" ? 1 : 0,
        current_page: res.media_type === "book" ? 10 : 0,
        rewatch_count: res.media_type === "movie" ? 1 : 0,
        tags: [res.media_type]
      };
      const created = await collection.create(payload);
      setItems([created, ...items]);
      setShowAddModal(false);
      showToast(`Added "${res.title}" to your collection!`);
    } catch (err) {
      showToast(`Add error: ${err.message}`, "error");
    }
  };

  // Manual Add Submit
  const handleManualAddSubmit = async (e) => {
    e.preventDefault();
    if (!manualTitle.trim()) return;
    try {
      const genresList = manualGenres.split(",").map(g => g.trim()).filter(Boolean);
      const media = {
        media_type: manualType,
        title: manualTitle.trim(),
        release_year: parseInt(manualYear, 10) || new Date().getFullYear(),
        poster_url: manualPoster.trim() || "https://images.unsplash.com/photo-1511512578047-dfb367046420?auto=format&fit=crop&w=600&q=80",
        backdrop_url: manualPoster.trim() || "https://images.unsplash.com/photo-1511512578047-dfb367046420?auto=format&fit=crop&w=1200&q=80",
        summary: manualOverview.trim() || `Custom ${manualType} tracked in HostCart.`,
        genres: genresList,
        creators: manualCreator ? [manualCreator.trim()] : [],
        total_episodes: manualType === "tv_show" ? parseInt(manualTotalMetric, 10) || 12 : null,
        total_pages: manualType === "book" ? parseInt(manualTotalMetric, 10) || 300 : null,
        runtime_minutes: manualType === "movie" ? parseInt(manualTotalMetric, 10) || 120 : null,
      };

      const payload = {
        media,
        status: manualStatus,
        rating: parseFloat(manualRating) || 9.0,
        is_favorite: false,
        playtime_hours: manualType === "game" ? 2.0 : 0.0,
        current_episode: manualType === "tv_show" ? 1 : 0,
        current_page: manualType === "book" ? 15 : 0,
        rewatch_count: manualType === "movie" ? 1 : 0,
        tags: [manualType]
      };

      const created = await collection.create(payload);
      setItems([created, ...items]);
      setShowAddModal(false);
      setManualTitle("");
      setManualCreator("");
      setManualPoster("");
      setManualOverview("");
      showToast(`Created custom entry "${manualTitle}"!`);
    } catch (err) {
      showToast(`Create error: ${err.message}`, "error");
    }
  };

  // Open Edit Modal
  const handleOpenEdit = (item) => {
    setSelectedItem(item);
    setEditForm({
      status: item.status,
      rating: item.rating !== null ? item.rating : 9.0,
      is_favorite: !!item.is_favorite,
      playtime_hours: item.playtime_hours || 0,
      current_episode: item.current_episode || 0,
      current_page: item.current_page || 0,
      rewatch_count: item.rewatch_count || 0,
      notes: item.notes || "",
      tags: (item.tags || []).join(", ")
    });
  };

  // Save Edit
  const handleSaveEdit = async (e) => {
    e.preventDefault();
    if (!selectedItem || !editForm) return;
    try {
      const updates = {
        status: editForm.status,
        rating: parseFloat(editForm.rating),
        is_favorite: editForm.is_favorite,
        playtime_hours: parseFloat(editForm.playtime_hours) || 0,
        current_episode: parseInt(editForm.current_episode, 10) || 0,
        current_page: parseInt(editForm.current_page, 10) || 0,
        rewatch_count: parseInt(editForm.rewatch_count, 10) || 0,
        notes: editForm.notes,
        tags: editForm.tags.split(",").map(t => t.trim()).filter(Boolean)
      };
      const updated = await collection.update(selectedItem.id, updates);
      setItems(prev => prev.map(i => i.id === selectedItem.id ? updated : i));
      setSelectedItem(null);
      showToast("Updated collection entry successfully!");
    } catch (err) {
      showToast(`Update failed: ${err.message}`, "error");
    }
  };

  // Delete Entry
  const handleDeleteEntry = async (id, e) => {
    if (e) e.stopPropagation();
    if (!window.confirm("Remove this entry from your collection?")) return;
    try {
      await collection.remove(id);
      setItems(prev => prev.filter(i => i.id !== id));
      if (selectedItem?.id === id) setSelectedItem(null);
      showToast("Entry deleted.");
    } catch (err) {
      showToast(`Delete failed: ${err.message}`, "error");
    }
  };

  // Save Runtime Settings
  const handleSaveSettings = async (e) => {
    e.preventDefault();
    if (!runtimeSettings) return;
    try {
      setSettingsLoading(true);
      const res = await settings.updateSettings(runtimeSettings);
      setRuntimeSettings(res.config || res);
      setSettingsMessage("Settings saved successfully!");
      setTimeout(() => setSettingsMessage(""), 4000);
      showToast("Configuration saved!");
    } catch (err) {
      showToast(`Settings error: ${err.message}`, "error");
    } finally {
      setSettingsLoading(false);
    }
  };

  // File Import handler
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const formData = new FormData();
      formData.append("file", file);
      showToast(`Importing ${file.name}...`, "info");
      const res = await importExport.importData(formData, true, true);
      showToast(`Imported ${res.imported_count || res.imported || 0} entries!`);
      const refreshed = await collection.list();
      setItems(refreshed);
    } catch (err) {
      showToast(`Import failed: ${err.message}`, "error");
    }
  };

  // Computed display items
  const heroItems = useMemo(() => {
    const pool = items.filter(i => i.status === "in_progress" || i.is_favorite || i.rating >= 9.0);
    return pool.length > 0 ? pool : items;
  }, [items]);

  const currentHero = heroItems[heroIndex % (heroItems.length || 1)] || items[0] || null;

  // Filtered Collection
  const filteredCollection = useMemo(() => {
    return items.filter(item => {
      const m = item.media || {};
      const type = m.media_type;

      // Sidebar type filter
      if (activeNav !== "all" && ["game", "movie", "tv_show", "book"].includes(activeNav) && type !== activeNav) {
        return false;
      }

      // Search bar filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const titleMatch = m.title && m.title.toLowerCase().includes(q);
        const creatorMatch = m.creators && m.creators.some(c => c.toLowerCase().includes(q));
        if (!titleMatch && !creatorMatch) return false;
      }

      // Status pill tabs
      if (activeTab === "in_progress") return item.status === "in_progress";
      if (activeTab === "completed") return item.status === "completed";
      if (activeTab === "plan_to") return item.status === "plan_to";
      if (activeTab === "wishlist") return item.status === "wishlist";
      if (activeTab === "top_rated") return (item.rating || 0) >= 9.3;

      return true;
    });
  }, [items, activeNav, activeTab, searchQuery]);

  // Quick Stats
  const totalGamingHours = useMemo(() => {
    return items
      .filter(i => i.media?.media_type === "game")
      .reduce((s, i) => s + (i.playtime_hours || 0), 0);
  }, [items]);

  const completedCount = useMemo(() => {
    return items.filter(i => i.status === "completed").length;
  }, [items]);

  const curatorXPAndLevel = useMemo(() => {
    const epsWatched = items
      .filter(i => i.media?.media_type === "tv_show")
      .reduce((s, i) => s + (i.current_episode || 0), 0);
    const pagesRead = items
      .filter(i => i.media?.media_type === "book")
      .reduce((s, i) => s + (i.current_page || 0), 0);
    const xp = Math.floor(
      items.length * 10 +
      completedCount * 25 +
      Math.floor(totalGamingHours * 2) +
      epsWatched * 5 +
      Math.floor(pagesRead * 0.1)
    );
    const level = Math.max(1, Math.floor(xp / 100) + 1);
    const filledSegments = Math.min(4, Math.max(1, Math.ceil(((xp % 100) / 100) * 4)));
    return { xp, level, filledSegments };
  }, [items, completedCount, totalGamingHours]);

  const activeWaveItem = useMemo(() => {
    return items.find(i => i.status === "in_progress") || items[0] || null;
  }, [items]);

  // Metric helper for cards
  const getMetricString = (item) => {
    const mt = item.media?.media_type;
    if (mt === "game") return `${item.playtime_hours || 0} hrs played`;
    if (mt === "movie") return item.status === "completed" ? "Watched" : `${item.media?.runtime_minutes || 120} min`;
    if (mt === "tv_show") return `Episode ${item.current_episode || 0} / ${item.media?.total_episodes || "?"}`;
    if (mt === "book") return `${item.current_page || 0} / ${item.media?.total_pages || "?"} pages`;
    return item.status;
  };

  const getProgressPct = (item) => {
    const mt = item.media?.media_type;
    if (item.status === "completed") return 100;
    if (mt === "tv_show" && item.media?.total_episodes) {
      return Math.min(100, Math.round(((item.current_episode || 0) / item.media.total_episodes) * 100));
    }
    if (mt === "book" && item.media?.total_pages) {
      return Math.min(100, Math.round(((item.current_page || 0) / item.media.total_pages) * 100));
    }
    if (mt === "game") {
      return Math.min(100, Math.round(((item.playtime_hours || 0) / 45) * 100));
    }
    return item.status === "in_progress" ? 50 : 0;
  };

  return (
    <div className="min-h-screen ambient-bg flex items-center justify-center p-2 md:p-5 selection:bg-red-500/30 selection:text-white">
      {/* Toast Notification */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-5 py-3 rounded-2xl shadow-2xl backdrop-blur-xl border text-sm font-semibold transition-all duration-300 ${
            toast.type === "error"
              ? "bg-red-950/90 border-red-500 text-red-200"
              : toast.type === "info"
              ? "bg-zinc-900/90 border-cyan-500 text-cyan-200"
              : "bg-zinc-900/90 border-emerald-500 text-emerald-200"
          }`}
        >
          {toast.type === "error" ? <X className="w-5 h-5 text-red-400" /> : <Sparkles className="w-5 h-5 text-emerald-400" />}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Main Container */}
      <div className="w-full max-w-[1540px] bg-[#181313]/95 border border-white/10 rounded-[28px] shadow-2xl overflow-hidden flex flex-col md:flex-row min-h-[900px] backdrop-blur-xl">

        {/* LEFT NAVIGATION SIDEBAR */}
        <aside className="w-full md:w-64 bg-[#141010] border-r border-white/[0.06] flex flex-col justify-between p-6 select-none shrink-0">
          <div>
            {/* Logo */}
            <div className="flex items-center gap-3 px-2 mb-8">
              <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-red-500 to-rose-600 flex items-center justify-center shadow-lg shadow-red-500/30">
                <span className="text-white font-extrabold text-xl tracking-tighter">H</span>
              </div>
              <div>
                <span className="text-xl font-extrabold tracking-wider text-white uppercase block leading-none">
                  HostCart
                </span>
                <span className="text-[10px] tracking-widest text-red-400 font-bold uppercase">
                  Media Engine
                </span>
              </div>
            </div>

            {/* Navigation Links */}
            <nav className="space-y-1">
              {[
                { id: "all", label: "Dashboard", icon: LayoutDashboard },
                { id: "stats", label: "Statistics", icon: BarChart3 },
                { id: "game", label: "Video Games", icon: Gamepad2 },
                { id: "movie", label: "Movies", icon: Film },
                { id: "tv_show", label: "TV Shows", icon: Tv },
                { id: "book", label: "Books", icon: BookOpen },
                { id: "import", label: "Import / Export", icon: DownloadCloud },
                { id: "settings", label: "API Settings", icon: SettingsIcon },
              ].map(nav => {
                const active = activeNav === nav.id;
                const IconComponent = nav.icon;
                return (
                  <button
                    key={nav.id}
                    onClick={() => setActiveNav(nav.id)}
                    className={`w-full flex items-center gap-3.5 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                      active
                        ? "sidebar-active text-white shadow-sm font-bold"
                        : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]"
                    }`}
                  >
                    <IconComponent className={`w-4 h-4 ${active ? "text-red-400" : "text-zinc-400"}`} />
                    <span>{nav.label}</span>
                  </button>
                );
              })}
            </nav>

            {/* Active Media Pulse */}
            <div className="mt-8 pt-6 border-t border-white/[0.06] hidden lg:block">
              <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 px-2 mb-4 flex items-center justify-between">
                <span>Active Pulse</span>
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              </p>
              <div className="space-y-3 px-1 text-xs">
                <div className="flex items-center justify-between text-zinc-300">
                  <span className="flex items-center gap-2">
                    <span className="text-red-400">🎮</span> Games
                  </span>
                  <span className="font-bold text-white">
                    {items.filter(i => i.media?.media_type === "game").length} items
                  </span>
                </div>
                <div className="flex items-center justify-between text-zinc-300">
                  <span className="flex items-center gap-2">
                    <span className="text-amber-400">🎬</span> Movies
                  </span>
                  <span className="font-bold text-white">
                    {items.filter(i => i.media?.media_type === "movie").length} items
                  </span>
                </div>
                <div className="flex items-center justify-between text-zinc-300">
                  <span className="flex items-center gap-2">
                    <span className="text-cyan-400">📺</span> Series
                  </span>
                  <span className="font-bold text-white">
                    {items.filter(i => i.media?.media_type === "tv_show").length} items
                  </span>
                </div>
                <div className="flex items-center justify-between text-zinc-300">
                  <span className="flex items-center gap-2">
                    <span className="text-emerald-400">📚</span> Books
                  </span>
                  <span className="font-bold text-white">
                    {items.filter(i => i.media?.media_type === "book").length} items
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* User Profile Card & Curator Level */}
          <div className="pt-5 border-t border-white/[0.06]">
            {currentUser ? (
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-red-500 to-rose-400 p-0.5 shrink-0">
                  <div className="w-full h-full rounded-2xl bg-[#1a1414] flex items-center justify-center text-sm font-bold text-white">
                    {currentUser.username.slice(0, 2).toUpperCase()}
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-bold text-white truncate">
                      {currentUser.username}
                    </p>
                    <button
                      onClick={handleLogout}
                      title="Log Out"
                      className="text-zinc-500 hover:text-red-400 transition"
                    >
                      <LogOut className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="flex gap-1 my-1.5">
                    {[0, 1, 2, 3].map(seg => (
                      <span
                        key={seg}
                        className={`h-1 flex-1 rounded-full ${
                          seg < curatorXPAndLevel.filledSegments ? "bg-red-500" : "bg-white/20"
                        }`}
                      />
                    ))}
                  </div>
                  <p className="text-[11px] text-zinc-400 font-medium">
                    Curator Lv. {curatorXPAndLevel.level} ({curatorXPAndLevel.xp} XP) • {currentUser.is_admin ? "Admin" : "Curator"}
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <button
                  onClick={() => { setAuthMode("login"); setShowAuthModal(true); }}
                  className="w-full bg-red-500 hover:bg-red-600 text-white font-bold text-xs py-2.5 rounded-xl transition shadow-lg shadow-red-500/25 flex items-center justify-center gap-2"
                >
                  <UserIcon className="w-4 h-4" />
                  <span>Sign In / Register</span>
                </button>
                <p className="text-[11px] text-zinc-500 text-center">
                  Sign in to track your library
                </p>
              </div>
            )}
          </div>
        </aside>

        {/* MAIN CONTENT AREA */}
        <main className="flex-1 p-5 md:p-8 overflow-y-auto custom-scroll space-y-7">

          {/* TOP HEADER BAR */}
          <header className="flex flex-wrap items-center justify-between gap-4">
            {/* Search Bar */}
            <div className="relative w-full max-w-md">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500 w-4 h-4" />
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Filter by title, creator, genre..."
                className="w-full bg-[#221b1b] border border-white/[0.08] focus:border-red-500/60 rounded-full pl-11 pr-4 py-2.5 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none transition shadow-inner"
              />
            </div>

            {/* Quick Stats Pills & Action Buttons */}
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2 bg-[#231c1c] border border-white/[0.08] px-4 py-2 rounded-full">
                <Clock className="w-4 h-4 text-amber-400" />
                <span className="text-sm font-bold text-white">{totalGamingHours}h Gaming</span>
              </div>
              <div className="flex items-center gap-2 bg-[#231c1c] border border-white/[0.08] px-4 py-2 rounded-full">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-sm font-bold text-white">{completedCount} Completed</span>
              </div>

              {/* Demo Seed Button */}
              {items.length === 0 && (
                <button
                  onClick={handleSeedDemo}
                  className="bg-zinc-800 hover:bg-zinc-700 border border-white/20 text-white text-xs font-bold px-4 py-2.5 rounded-full transition flex items-center gap-2"
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>Seed Demo Collection</span>
                </button>
              )}

              {/* Add Media Button */}
              <button
                onClick={() => setShowAddModal(true)}
                className="bg-gradient-to-r from-red-500 to-rose-600 hover:from-red-600 hover:to-rose-700 text-white text-sm font-semibold px-5 py-2.5 rounded-full shadow-lg shadow-red-500/30 transition flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                <span>Add Media</span>
              </button>
            </div>
          </header>

          {/* VIEW ROUTING BASED ON activeNav */}
          {activeNav === "stats" ? (
            <StatisticsView fallbackItems={items} />
          ) : activeNav === "import" ? (
            /* IMPORT / EXPORT VIEW */
            <div className="bg-[#211a1a] border border-white/10 rounded-3xl p-8 space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                  <DownloadCloud className="w-6 h-6 text-red-400" />
                  <span>Import & Export Collection</span>
                </h2>
                <p className="text-sm text-zinc-400 mt-1">
                  Take full ownership of your data. Export your entire library in JSON or CSV, or restore from external backups.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                {/* Export Card */}
                <div className="bg-[#181313] border border-white/10 rounded-2xl p-6 space-y-4">
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <span>⬇</span> Export Collection Data
                  </h3>
                  <p className="text-xs text-zinc-400">
                    Download all {items.length} media entries including ratings, status, tags, and progress logs.
                  </p>
                  <div className="flex flex-wrap gap-3 pt-2">
                    <button
                      onClick={() => importExport.exportData("json")}
                      className="bg-white hover:bg-zinc-200 text-black font-bold text-xs px-5 py-2.5 rounded-full transition flex items-center gap-2"
                    >
                      <span>Download JSON</span>
                    </button>
                    <button
                      onClick={() => importExport.exportData("csv")}
                      className="bg-white/10 hover:bg-white/20 text-white font-bold text-xs px-5 py-2.5 rounded-full transition flex items-center gap-2"
                    >
                      <span>Download CSV</span>
                    </button>
                  </div>
                </div>

                {/* Import Card */}
                <div className="bg-[#181313] border border-white/10 rounded-2xl p-6 space-y-4">
                  <h3 className="text-lg font-bold text-white flex items-center gap-2">
                    <span>⬆</span> Batch Import (.json / .csv)
                  </h3>
                  <p className="text-xs text-zinc-400">
                    Upload a HostCart JSON or CSV file. Existing catalog items and external IDs are automatically deduplicated.
                  </p>
                  <label className="inline-flex items-center gap-2 bg-red-500 hover:bg-red-600 text-white font-bold text-xs px-5 py-2.5 rounded-full cursor-pointer transition shadow-lg shadow-red-500/20">
                    <Upload className="w-4 h-4" />
                    <span>Select File to Import</span>
                    <input
                      type="file"
                      accept=".json,.csv"
                      onChange={handleFileUpload}
                      className="hidden"
                    />
                  </label>
                </div>
              </div>
            </div>
          ) : activeNav === "settings" ? (
            /* RUNTIME SETTINGS VIEW */
            <div className="bg-[#211a1a] border border-white/10 rounded-3xl p-8 space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold text-white flex items-center gap-2">
                    <SettingsIcon className="w-6 h-6 text-red-400" />
                    <span>External Metadata Providers & Settings</span>
                  </h2>
                  <p className="text-sm text-zinc-400 mt-1">
                    Manage IGDB, TMDB, and Google Books keys. Changes are persisted dynamically.
                  </p>
                </div>
                {settingsMessage && (
                  <span className="text-xs bg-emerald-500/20 text-emerald-300 px-3 py-1.5 rounded-full font-semibold border border-emerald-500/30">
                    {settingsMessage}
                  </span>
                )}
              </div>

              {!currentUser?.is_admin ? (
                <div className="bg-red-950/40 border border-red-500/40 rounded-2xl p-6 text-center space-y-2">
                  <Shield className="w-8 h-8 text-red-400 mx-auto" />
                  <p className="text-sm font-bold text-white">Administrator Access Required</p>
                  <p className="text-xs text-zinc-400">
                    You must sign in with an administrator account to view or modify backend runtime settings.
                  </p>
                </div>
              ) : settingsLoading ? (
                <div className="py-12 text-center text-zinc-400">Loading settings...</div>
              ) : (
                <form onSubmit={handleSaveSettings} className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                    {/* IGDB Card */}
                    <div className="bg-[#181313] border border-white/10 rounded-2xl p-5 space-y-3">
                      <span className="text-xs px-2.5 py-1 rounded-full bg-red-500/20 text-red-300 font-semibold inline-block">
                        🎮 IGDB (Twitch OAuth)
                      </span>
                      <div className="space-y-1">
                        <label className="text-[11px] text-zinc-400 uppercase font-semibold">Client ID</label>
                        <input
                          type="text"
                          value={runtimeSettings?.providers?.igdb?.client_id || ""}
                          onChange={e => setRuntimeSettings({
                            ...runtimeSettings,
                            providers: {
                              ...runtimeSettings.providers,
                              igdb: { ...runtimeSettings.providers?.igdb, client_id: e.target.value }
                            }
                          })}
                          placeholder="Twitch Client ID"
                          className="w-full bg-[#221b1b] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[11px] text-zinc-400 uppercase font-semibold">Client Secret</label>
                        <input
                          type="password"
                          value={runtimeSettings?.providers?.igdb?.client_secret || ""}
                          onChange={e => setRuntimeSettings({
                            ...runtimeSettings,
                            providers: {
                              ...runtimeSettings.providers,
                              igdb: { ...runtimeSettings.providers?.igdb, client_secret: e.target.value }
                            }
                          })}
                          placeholder="Twitch Client Secret"
                          className="w-full bg-[#221b1b] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                        />
                      </div>
                    </div>

                    {/* TMDB Card */}
                    <div className="bg-[#181313] border border-white/10 rounded-2xl p-5 space-y-3">
                      <span className="text-xs px-2.5 py-1 rounded-full bg-amber-500/20 text-amber-300 font-semibold inline-block">
                        🎬 TMDB (Movies & TV)
                      </span>
                      <div className="space-y-1">
                        <label className="text-[11px] text-zinc-400 uppercase font-semibold">API Key / Token</label>
                        <input
                          type="password"
                          value={runtimeSettings?.providers?.tmdb?.api_key || ""}
                          onChange={e => setRuntimeSettings({
                            ...runtimeSettings,
                            providers: {
                              ...runtimeSettings.providers,
                              tmdb: { ...runtimeSettings.providers?.tmdb, api_key: e.target.value }
                            }
                          })}
                          placeholder="TMDB API Key"
                          className="w-full bg-[#221b1b] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                        />
                      </div>
                      <p className="text-[11px] text-zinc-500">
                        Used for movie & series posters, episode totals, and release years.
                      </p>
                    </div>

                    {/* Books Card */}
                    <div className="bg-[#181313] border border-white/10 rounded-2xl p-5 space-y-3">
                      <span className="text-xs px-2.5 py-1 rounded-full bg-emerald-500/20 text-emerald-300 font-semibold inline-block">
                        📚 OpenLibrary & Google Books
                      </span>
                      <div className="space-y-1">
                        <label className="text-[11px] text-zinc-400 uppercase font-semibold">Google Books Key (Optional)</label>
                        <input
                          type="password"
                          value={runtimeSettings?.providers?.books?.google_books_api_key || ""}
                          onChange={e => setRuntimeSettings({
                            ...runtimeSettings,
                            providers: {
                              ...runtimeSettings.providers,
                              books: { ...runtimeSettings.providers?.books, google_books_api_key: e.target.value }
                            }
                          })}
                          placeholder="Google Books Key"
                          className="w-full bg-[#221b1b] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                        />
                      </div>
                      <p className="text-[11px] text-emerald-400">
                        ✓ OpenLibrary works out of the box with zero configuration.
                      </p>
                    </div>
                  </div>

                  <div className="flex justify-end pt-2">
                    <button
                      type="submit"
                      disabled={settingsLoading}
                      className="bg-red-500 hover:bg-red-600 text-white font-bold text-xs px-6 py-2.5 rounded-full transition shadow-lg shadow-red-500/25"
                    >
                      {settingsLoading ? "Saving..." : "Save Settings"}
                    </button>
                  </div>
                </form>
              )}
            </div>
          ) : (
            /* COLLECTION & DASHBOARD VIEW */
            <>
              {/* TOP HERO ROW (Carousels) */}
              {currentHero && (
                <section className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                  {/* Hero Left 8 Cols */}
                  <div className="lg:col-span-8 relative h-[350px] rounded-[26px] overflow-hidden border border-white/10 group shadow-2xl">
                    <img
                      src={currentHero.media?.backdrop_url || currentHero.media?.poster_url}
                      alt={currentHero.media?.title}
                      className="w-full h-full object-cover object-center group-hover:scale-105 transition-transform duration-700"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/40 to-black/10" />
                    <div className="absolute inset-0 bg-gradient-to-r from-black/80 via-transparent to-transparent" />

                    {/* Badge */}
                    <div className="absolute top-5 left-5 flex items-center gap-2 bg-white/15 backdrop-blur-md border border-white/20 px-3.5 py-1.5 rounded-full text-xs font-semibold text-white">
                      <span>{TYPE_CONFIG[currentHero.media?.media_type]?.icon}</span>
                      <span>{getMetricString(currentHero)}</span>
                    </div>

                    {/* Hero Info */}
                    <div className="absolute bottom-6 left-6 right-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
                      <div className="space-y-1.5 max-w-md">
                        <span className="text-[11px] uppercase tracking-widest text-red-400 font-bold">
                          Featured {TYPE_CONFIG[currentHero.media?.media_type]?.label}
                        </span>
                        <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight text-white uppercase leading-none truncate">
                          {currentHero.media?.title}
                        </h1>
                        <p className="text-xs font-semibold tracking-wider text-zinc-300 uppercase truncate">
                          — {currentHero.media?.creators?.join(", ") || `${currentHero.media?.release_year || ""}`}
                        </p>

                        <div className="pt-3 flex items-center gap-3">
                          <button
                            onClick={(e) => handleQuickIncrement(currentHero.id, e)}
                            className="bg-white hover:bg-zinc-200 text-zinc-950 font-bold text-xs px-5 py-3 rounded-full shadow-lg transition flex items-center gap-2"
                          >
                            <span>Log Progress</span>
                            <span>▶</span>
                          </button>
                          <button
                            onClick={() => handleOpenEdit(currentHero)}
                            className="bg-white/15 hover:bg-white/25 backdrop-blur-md border border-white/15 text-white font-semibold text-xs px-5 py-3 rounded-full transition"
                          >
                            Edit / Details
                          </button>
                        </div>
                      </div>

                      {/* Dots */}
                      <div className="flex items-center gap-1.5 pb-1">
                        {heroItems.slice(0, 5).map((h, i) => (
                          <button
                            key={h.id}
                            onClick={() => setHeroIndex(i)}
                            className={`h-1.5 rounded-full transition-all ${
                              i === heroIndex % Math.min(5, heroItems.length)
                                ? "w-7 bg-white"
                                : "w-1.5 bg-white/40 hover:bg-white/70"
                            }`}
                          />
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Hero Right 4 Cols: Active Wave Card & Currently Tracking */}
                  <div className="lg:col-span-4 flex flex-col gap-5">
                    {/* Wave Card */}
                    {activeWaveItem && (
                      <div className="wave-card rounded-[22px] border border-white/10 p-4 flex items-center justify-between h-[96px] shadow-lg">
                        <div
                          className="absolute inset-y-0 left-0 bg-gradient-to-r from-red-500 to-rose-500 transition-all duration-500 opacity-90"
                          style={{ width: `${Math.max(25, getProgressPct(activeWaveItem))}%` }}
                        />
                        <div className="relative z-10 flex items-center gap-3.5 min-w-0">
                          <img
                            src={activeWaveItem.media?.poster_url}
                            alt={activeWaveItem.media?.title}
                            className="w-12 h-12 rounded-xl object-cover ring-2 ring-white/20 shadow shrink-0"
                          />
                          <div className="min-w-0">
                            <p className="text-sm font-extrabold text-white drop-shadow-sm truncate max-w-[170px]">
                              {activeWaveItem.media?.title}
                            </p>
                            <p className="text-xs font-semibold text-white/90 truncate max-w-[170px]">
                              {getProgressPct(activeWaveItem)}% • {getMetricString(activeWaveItem)}
                            </p>
                          </div>
                        </div>
                        <button
                          onClick={(e) => handleQuickIncrement(activeWaveItem.id, e)}
                          title="Quick Increment (+)"
                          className="relative z-10 w-9 h-9 rounded-xl bg-black/40 hover:bg-black/60 border border-white/20 text-white flex items-center justify-center text-sm font-bold transition shrink-0"
                        >
                          ＋
                        </button>
                      </div>
                    )}

                    {/* Currently Tracking Queue */}
                    <div className="flex-1 bg-[#201919] border border-white/[0.07] rounded-[24px] p-5 flex flex-col justify-between">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
                          <Flame className="w-4 h-4 text-red-400" />
                          <span>Currently Tracking</span>
                        </h3>
                        <button onClick={() => setActiveNav("stats")} className="text-xs text-red-400 hover:underline">
                          Stats ↗
                        </button>
                      </div>
                      <div className="space-y-3.5">
                        {items.filter(i => i.status === "in_progress").slice(0, 3).map(item => (
                          <div
                            key={item.id}
                            onClick={() => handleOpenEdit(item)}
                            className="flex items-center justify-between gap-3 group cursor-pointer"
                          >
                            <div className="flex items-center gap-3 min-w-0">
                              <img
                                src={item.media?.poster_url}
                                alt={item.media?.title}
                                className="w-10 h-10 rounded-xl object-cover shrink-0 group-hover:ring-2 ring-red-500/60 transition"
                              />
                              <div className="min-w-0">
                                <p className="text-xs font-bold text-zinc-100 truncate group-hover:text-red-400 transition">
                                  {item.media?.title}
                                </p>
                                <p className="text-[11px] text-zinc-500 truncate">
                                  {getMetricString(item)}
                                </p>
                              </div>
                            </div>
                            <button
                              onClick={(e) => handleQuickIncrement(item.id, e)}
                              className="px-2.5 py-1 rounded-full bg-white/[0.06] hover:bg-red-500/20 hover:text-red-300 text-[11px] font-semibold text-zinc-300 transition shrink-0"
                            >
                              +1
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </section>
              )}

              {/* MIDDLE 4-COLUMN QUICK RESUME & HIGHLIGHTS STRIP */}
              {items.length > 0 && (
                <section className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-base font-bold text-white flex items-center gap-2">
                      <span>Quick Resume & Highlights</span>
                      <span className="text-xs font-normal text-zinc-500">Top active & highest-rated entries</span>
                    </h2>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {items.slice(0, 4).map(item => {
                      const m = item.media || {};
                      const type = m.media_type;
                      return (
                        <div
                          key={`highlight-${item.id}`}
                          onClick={() => handleOpenEdit(item)}
                          className="bg-[#201919] hover:bg-[#281f1f] border border-white/[0.06] hover:border-red-500/30 rounded-2xl p-3 flex items-center gap-3.5 cursor-pointer transition group"
                        >
                          <img
                            src={m.poster_url || m.backdrop_url}
                            alt={m.title}
                            className="w-14 h-14 rounded-xl object-cover shrink-0 shadow"
                          />
                          <div className="min-w-0 flex-1">
                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${TYPE_CONFIG[type]?.bg}`}>
                              {TYPE_CONFIG[type]?.icon} {TYPE_CONFIG[type]?.label.slice(0, -1) || type}
                            </span>
                            <h4 className="text-xs font-bold text-white truncate mt-1 group-hover:text-red-400 transition">
                              {m.title}
                            </h4>
                            <p className="text-[11px] text-zinc-400 truncate">
                              ★ {item.rating !== null ? item.rating : "—"} • {getMetricString(item)}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}

              {/* POSTER GRID SECTION */}
              <section className="space-y-4">
                {/* Header & Tabs */}
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <h2 className="text-base font-bold text-white">
                    {TYPE_CONFIG[activeNav]?.label || "Collection"} Library ({filteredCollection.length})
                  </h2>
                </div>

                {/* Status Tabs */}
                <div className="flex items-center gap-7 border-b border-white/[0.08] text-xs font-semibold overflow-x-auto">
                  {[
                    { id: "all", label: "All Entries" },
                    { id: "in_progress", label: "In Progress" },
                    { id: "top_rated", label: "Top Rated (9.3+)" },
                    { id: "plan_to", label: "Backlog / Plan To" },
                    { id: "completed", label: "Completed" },
                    { id: "wishlist", label: "Wishlist" },
                  ].map(tab => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`pb-3 transition whitespace-nowrap border-b-2 ${
                        activeTab === tab.id
                          ? "border-red-500 text-white font-bold"
                          : "border-transparent text-zinc-500 hover:text-zinc-300"
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                {/* Grid Cards */}
                {filteredCollection.length === 0 ? (
                  <div className="py-16 text-center border border-dashed border-white/10 rounded-3xl p-8 space-y-3">
                    <p className="text-sm font-semibold text-zinc-400">No media found matching this filter.</p>
                    <button
                      onClick={handleSeedDemo}
                      className="bg-red-500 hover:bg-red-600 text-white font-bold text-xs px-5 py-2.5 rounded-full transition"
                    >
                      Click to Seed 10 Starter Items
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5 pt-1">
                    {filteredCollection.map(item => {
                      const m = item.media || {};
                      const type = m.media_type;
                      const pct = getProgressPct(item);
                      return (
                        <div
                          key={item.id}
                          onClick={() => handleOpenEdit(item)}
                          className="group relative h-60 rounded-[22px] overflow-hidden border border-white/10 hover:border-red-500/40 cursor-pointer shadow-lg transition-all duration-300"
                        >
                          <img
                            src={m.poster_url || m.backdrop_url}
                            alt={m.title}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                          />
                          <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/40 to-transparent" />

                          {/* Top Badges */}
                          <div className="absolute top-3 left-3 right-3 flex items-center justify-between">
                            <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full backdrop-blur-md ${TYPE_CONFIG[type]?.bg}`}>
                              {TYPE_CONFIG[type]?.icon} {TYPE_CONFIG[type]?.label.slice(0, -1) || type}
                            </span>
                            <span className="text-[11px] font-bold px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-md text-amber-300 flex items-center gap-1">
                              <Star className="w-3 h-3 fill-amber-300" />
                              <span>{item.rating !== null ? item.rating : "—"}</span>
                            </span>
                          </div>

                          {/* Bottom Info & Quick Increment */}
                          <div className="absolute bottom-3.5 left-4 right-4 space-y-1.5">
                            <p className="text-base font-extrabold text-white leading-tight truncate">
                              {m.title}
                            </p>
                            <div className="flex items-center justify-between text-[11px] text-zinc-300">
                              <span className="truncate max-w-[150px]">{getMetricString(item)}</span>
                              <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition">
                                <button
                                  onClick={(e) => handleQuickIncrement(item.id, e)}
                                  className="bg-red-500 hover:bg-red-600 text-white font-bold px-2.5 py-0.5 rounded-full text-[10px] transition"
                                >
                                  +1
                                </button>
                                <button
                                  onClick={(e) => handleDeleteEntry(item.id, e)}
                                  className="p-1 rounded-full bg-black/60 hover:bg-red-500/80 text-zinc-400 hover:text-white transition"
                                  title="Delete entry"
                                >
                                  <Trash2 className="w-3 h-3" />
                                </button>
                              </div>
                            </div>
                            <div className="w-full h-1 bg-white/20 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-gradient-to-r from-red-500 to-rose-400"
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>
            </>
          )}
        </main>
      </div>

      {/* ============================================================== */}
      {/* AUTH MODAL */}
      {/* ============================================================== */}
      {showAuthModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-[#201919] border border-white/10 rounded-3xl p-7 shadow-2xl relative space-y-5">
            <button
              onClick={() => setShowAuthModal(false)}
              className="absolute top-5 right-5 text-zinc-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="text-center space-y-1">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-red-500 to-rose-600 flex items-center justify-center mx-auto shadow-lg shadow-red-500/30">
                <span className="text-white font-black text-xl">H</span>
              </div>
              <h3 className="text-xl font-bold text-white">
                {authMode === "login" ? "Welcome Back to HostCart" : "Create HostCart Account"}
              </h3>
              <p className="text-xs text-zinc-400">
                Self-hosted Multi-Media Tracking & Statistics
              </p>
            </div>

            {authError && (
              <div className="bg-red-950/60 border border-red-500/40 rounded-xl p-3 text-xs text-red-300">
                {authError}
              </div>
            )}

            <form onSubmit={handleAuthSubmit} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-zinc-300">Username</label>
                <input
                  type="text"
                  required
                  value={authUsername}
                  onChange={e => setAuthUsername(e.target.value)}
                  placeholder="e.g. curator"
                  className="w-full bg-[#161212] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-red-500"
                />
              </div>

              {authMode === "register" && (
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-zinc-300">Email Address</label>
                  <input
                    type="email"
                    required
                    value={authEmail}
                    onChange={e => setAuthEmail(e.target.value)}
                    placeholder="curator@example.com"
                    className="w-full bg-[#161212] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-red-500"
                  />
                </div>
              )}

              <div className="space-y-1">
                <label className="text-xs font-semibold text-zinc-300">Password</label>
                <input
                  type="password"
                  required
                  value={authPassword}
                  onChange={e => setAuthPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-[#161212] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-red-500"
                />
              </div>

              <button
                type="submit"
                disabled={authSubmitting}
                className="w-full bg-gradient-to-r from-red-500 to-rose-600 hover:from-red-600 hover:to-rose-700 text-white font-bold text-sm py-3 rounded-xl transition shadow-lg shadow-red-500/25"
              >
                {authSubmitting ? "Processing..." : authMode === "login" ? "Sign In" : "Create Account"}
              </button>
            </form>

            <div className="text-center pt-2">
              <button
                onClick={() => {
                  setAuthMode(authMode === "login" ? "register" : "login");
                  setAuthError("");
                }}
                className="text-xs text-zinc-400 hover:text-white"
              >
                {authMode === "login" ? "Need an account? Register" : "Already have an account? Sign In"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* ADD MEDIA MODAL (Live Search & Manual Form) */}
      {/* ============================================================== */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-2xl bg-[#201919] border border-white/10 rounded-3xl p-7 shadow-2xl relative space-y-6 max-h-[90vh] overflow-y-auto custom-scroll">
            <button
              onClick={() => setShowAddModal(false)}
              className="absolute top-5 right-5 text-zinc-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <h3 className="text-xl font-bold text-white flex items-center gap-2">
                <Plus className="w-5 h-5 text-red-500" />
                <span>Add Media Entry</span>
              </h3>
              <div className="flex gap-2">
                <button
                  onClick={() => setAddTab("search")}
                  className={`px-4 py-1.5 rounded-full text-xs font-bold transition ${
                    addTab === "search" ? "bg-red-500 text-white" : "bg-white/5 text-zinc-400 hover:text-white"
                  }`}
                >
                  External Search
                </button>
                <button
                  onClick={() => setAddTab("manual")}
                  className={`px-4 py-1.5 rounded-full text-xs font-bold transition ${
                    addTab === "manual" ? "bg-red-500 text-white" : "bg-white/5 text-zinc-400 hover:text-white"
                  }`}
                >
                  Manual Entry
                </button>
              </div>
            </div>

            {addTab === "search" ? (
              <div className="space-y-4">
                <form onSubmit={handleExternalSearch} className="flex gap-2">
                  <select
                    value={searchType}
                    onChange={e => setSearchType(e.target.value)}
                    className="bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                  >
                    <option value="game">🎮 Games (IGDB)</option>
                    <option value="movie">🎬 Movies (TMDB)</option>
                    <option value="tv_show">📺 TV Shows (TMDB)</option>
                    <option value="book">📚 Books (OpenLibrary)</option>
                  </select>
                  <input
                    type="text"
                    required
                    value={searchQueryTerm}
                    onChange={e => setSearchQueryTerm(e.target.value)}
                    placeholder="Search title e.g. Cyberpunk, Dune, Arcane..."
                    className="flex-1 bg-[#161212] border border-white/10 rounded-xl px-4 py-2 text-xs text-white"
                  />
                  <button
                    type="submit"
                    disabled={isSearching}
                    className="bg-red-500 hover:bg-red-600 text-white font-bold text-xs px-5 py-2 rounded-xl transition"
                  >
                    {isSearching ? "Searching..." : "Search"}
                  </button>
                </form>

                {searchError && (
                  <p className="text-xs text-amber-400 bg-amber-400/10 p-2.5 rounded-xl border border-amber-400/20">
                    {searchError}
                  </p>
                )}

                <div className="space-y-3 max-h-[360px] overflow-y-auto custom-scroll">
                  {searchResults.map((res, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between gap-4 bg-[#181313] border border-white/[0.06] p-3 rounded-2xl hover:border-red-500/40 transition"
                    >
                      <div className="flex items-center gap-3.5 min-w-0">
                        <img
                          src={res.poster_url || "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=200&q=80"}
                          alt={res.title}
                          className="w-12 h-16 rounded-xl object-cover shrink-0"
                        />
                        <div className="min-w-0">
                          <p className="text-sm font-bold text-white truncate">{res.title}</p>
                          <p className="text-xs text-zinc-400 truncate">
                            {res.release_year || "Unknown Year"} • {res.genres?.slice(0, 2).join(", ") || "General"}
                          </p>
                          <p className="text-[11px] text-zinc-500 truncate max-w-md">{res.summary}</p>
                        </div>
                      </div>
                      <button
                        onClick={() => handleAddSearchResult(res)}
                        className="bg-white hover:bg-zinc-200 text-black font-bold text-xs px-4 py-2 rounded-full transition shrink-0"
                      >
                        + Add
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              /* MANUAL ADD FORM */
              <form onSubmit={handleManualAddSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-300">Title</label>
                    <input
                      type="text"
                      required
                      value={manualTitle}
                      onChange={e => setManualTitle(e.target.value)}
                      placeholder="e.g. Blade Runner 2049"
                      className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-300">Media Type</label>
                    <select
                      value={manualType}
                      onChange={e => setManualType(e.target.value)}
                      className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                    >
                      <option value="game">🎮 Video Game</option>
                      <option value="movie">🎬 Movie</option>
                      <option value="tv_show">📺 TV Show</option>
                      <option value="book">📚 Book</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-300">Creator / Studio</label>
                    <input
                      type="text"
                      value={manualCreator}
                      onChange={e => setManualCreator(e.target.value)}
                      placeholder="Developer / Director"
                      className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-300">Year</label>
                    <input
                      type="number"
                      value={manualYear}
                      onChange={e => setManualYear(e.target.value)}
                      className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-300">Initial Status</label>
                    <select
                      value={manualStatus}
                      onChange={e => setManualStatus(e.target.value)}
                      className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                    >
                      <option value="in_progress">In Progress</option>
                      <option value="completed">Completed</option>
                      <option value="plan_to">Plan To / Backlog</option>
                      <option value="wishlist">Wishlist</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-300">Poster Image URL</label>
                    <input
                      type="url"
                      value={manualPoster}
                      onChange={e => setManualPoster(e.target.value)}
                      placeholder="https://..."
                      className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-300">Genres (comma separated)</label>
                    <input
                      type="text"
                      value={manualGenres}
                      onChange={e => setManualGenres(e.target.value)}
                      placeholder="Sci-Fi, RPG"
                      className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-semibold text-zinc-300">Overview / Notes</label>
                  <textarea
                    rows={3}
                    value={manualOverview}
                    onChange={e => setManualOverview(e.target.value)}
                    placeholder="Short summary..."
                    className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                  />
                </div>

                <button
                  type="submit"
                  className="w-full bg-gradient-to-r from-red-500 to-rose-600 hover:from-red-600 hover:to-rose-700 text-white font-bold text-xs py-3 rounded-xl transition shadow-lg shadow-red-500/25"
                >
                  Create Collection Entry
                </button>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* EDIT / DETAIL MODAL */}
      {/* ============================================================== */}
      {selectedItem && editForm && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
          <div className="w-full max-w-xl bg-[#201919] border border-white/10 rounded-3xl p-7 shadow-2xl relative space-y-5">
            <button
              onClick={() => setSelectedItem(null)}
              className="absolute top-5 right-5 text-zinc-400 hover:text-white"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-4 border-b border-white/10 pb-4">
              <img
                src={selectedItem.media?.poster_url}
                alt={selectedItem.media?.title}
                className="w-14 h-20 rounded-xl object-cover"
              />
              <div>
                <h3 className="text-lg font-bold text-white">{selectedItem.media?.title}</h3>
                <p className="text-xs text-zinc-400">
                  {TYPE_CONFIG[selectedItem.media?.media_type]?.label} • {selectedItem.media?.release_year}
                </p>
              </div>
            </div>

            <form onSubmit={handleSaveEdit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-zinc-300">Status</label>
                  <select
                    value={editForm.status}
                    onChange={e => setEditForm({ ...editForm, status: e.target.value })}
                    className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                  >
                    <option value="in_progress">In Progress</option>
                    <option value="completed">Completed</option>
                    <option value="plan_to">Plan To / Backlog</option>
                    <option value="wishlist">Wishlist</option>
                    <option value="dropped">Dropped</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-zinc-300">Rating (0 - 10)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="10"
                    value={editForm.rating}
                    onChange={e => setEditForm({ ...editForm, rating: e.target.value })}
                    className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                  />
                </div>
              </div>

              {/* Progress metric specific to type */}
              <div className="grid grid-cols-2 gap-4">
                {selectedItem.media?.media_type === "game" && (
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-300">Playtime (Hours)</label>
                    <input
                      type="number"
                      step="0.5"
                      value={editForm.playtime_hours}
                      onChange={e => setEditForm({ ...editForm, playtime_hours: e.target.value })}
                      className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                    />
                  </div>
                )}
                {selectedItem.media?.media_type === "tv_show" && (
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-300">Current Episode</label>
                    <input
                      type="number"
                      value={editForm.current_episode}
                      onChange={e => setEditForm({ ...editForm, current_episode: e.target.value })}
                      className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                    />
                  </div>
                )}
                {selectedItem.media?.media_type === "book" && (
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-300">Current Page</label>
                    <input
                      type="number"
                      value={editForm.current_page}
                      onChange={e => setEditForm({ ...editForm, current_page: e.target.value })}
                      className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                    />
                  </div>
                )}
                {selectedItem.media?.media_type === "movie" && (
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-300">Rewatch Count</label>
                    <input
                      type="number"
                      value={editForm.rewatch_count}
                      onChange={e => setEditForm({ ...editForm, rewatch_count: e.target.value })}
                      className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                    />
                  </div>
                )}
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-zinc-300">Tags (comma separated)</label>
                  <input
                    type="text"
                    value={editForm.tags}
                    onChange={e => setEditForm({ ...editForm, tags: e.target.value })}
                    className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-zinc-300">Personal Notes & Review</label>
                <textarea
                  rows={3}
                  value={editForm.notes}
                  onChange={e => setEditForm({ ...editForm, notes: e.target.value })}
                  placeholder="Notes, thoughts, or review..."
                  className="w-full bg-[#161212] border border-white/10 rounded-xl px-3 py-2 text-xs text-white"
                />
              </div>

              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={() => handleDeleteEntry(selectedItem.id)}
                  className="text-red-400 hover:text-red-300 text-xs font-semibold flex items-center gap-1.5"
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Remove from Collection</span>
                </button>
                <button
                  type="submit"
                  className="bg-red-500 hover:bg-red-600 text-white font-bold text-xs px-6 py-2.5 rounded-full transition shadow-lg shadow-red-500/25"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
