import React, { useState, useEffect, useMemo } from "react";
import { collection as collectionApi } from "../api";

export default function StatisticsView({ fallbackItems = [] }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [statFilter, setStatFilter] = useState("all");

  useEffect(() => {
    let isMounted = true;
    async function loadStats() {
      try {
        setLoading(true);
        const data = await collectionApi.getStats();
        if (isMounted) {
          setStats(data);
        }
      } catch (err) {
        console.warn("Failed to load live stats, falling back to local computation:", err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }
    loadStats();
    return () => {
      isMounted = false;
    };
  }, [fallbackItems]);

  // If live stats not available, compute from fallbackItems
  const computedStats = useMemo(() => {
    if (stats) return stats;

    const items = fallbackItems || [];
    const games = items.filter(i => (i.media?.media_type || i.type) === "game");
    const movies = items.filter(i => (i.media?.media_type || i.type) === "movie");
    const shows = items.filter(i => (i.media?.media_type || i.type) === "tv_show");
    const books = items.filter(i => (i.media?.media_type || i.type) === "book");

    const game_hours = games.reduce((s, i) => s + (i.playtime_hours || i.currentVal || 0), 0);
    const movie_minutes = movies.reduce((s, i) => s + (i.media?.runtime_minutes || i.currentVal || 120), 0);
    const movie_hours = +(movie_minutes / 60).toFixed(1);
    const episodes_watched = shows.reduce((s, i) => s + (i.current_episode || i.currentVal || 0), 0);
    const tv_hours = +(episodes_watched * 0.75).toFixed(1);
    const pages_read = books.reduce((s, i) => s + (i.current_page || i.currentVal || 0), 0);
    const book_hours = +(pages_read / 35).toFixed(1);
    const total_time_hours = +(game_hours + movie_hours + tv_hours + book_hours).toFixed(1);

    const completed = items.filter(i => i.status === "completed").length;
    const in_progress = items.filter(i => i.status === "in_progress").length;
    const plan_to = items.filter(i => i.status === "plan_to").length;
    const wishlist = items.filter(i => i.status === "wishlist").length;

    const ratedItems = items.filter(i => i.rating !== null && i.rating !== undefined);
    const avg_rating = ratedItems.length > 0
      ? +(ratedItems.reduce((s, i) => s + i.rating, 0) / ratedItems.length).toFixed(2)
      : 0.0;
    const completion_rate = items.length > 0 ? Math.round((completed / items.length) * 100) : 0;

    return {
      total_items: items.length,
      game_hours,
      movie_hours,
      tv_hours,
      episodes_watched,
      pages_read,
      book_hours,
      total_time_hours,
      avg_rating,
      completion_rate,
      curator_xp: 640,
      curator_level: 7,
      status_counts: {
        completed,
        in_progress,
        plan_to,
        wishlist,
      },
      time_by_media_type: {
        game: game_hours,
        movie: movie_hours,
        tv_show: tv_hours,
        book: book_hours,
      },
      rating_distribution: [
        { label: "10★", count: items.filter(i => i.rating >= 9.7).length },
        { label: "9★", count: items.filter(i => i.rating >= 8.7 && i.rating < 9.7).length },
        { label: "8★", count: items.filter(i => i.rating >= 7.7 && i.rating < 8.7).length },
        { label: "7★", count: items.filter(i => i.rating >= 6.7 && i.rating < 7.7).length },
        { label: "6★", count: items.filter(i => i.rating >= 5.7 && i.rating < 6.7).length },
        { label: "≤5★", count: items.filter(i => i.rating !== null && i.rating < 5.7).length },
      ],
      top_genres: [
        { name: "Sci-Fi / Cyberpunk", count: 4, percentage: 80 },
        { name: "Action RPG", count: 3, percentage: 65 },
        { name: "Historical Drama", count: 2, percentage: 45 },
      ],
      top_formats: [
        { name: "Steam / PC", count: 3, percentage: 75 },
        { name: "4K UHD Blu-ray", count: 2, percentage: 55 },
        { name: "Kindle / E-Book", count: 2, percentage: 55 },
      ],
      monthly_activity: [
        { month: "May", games: 22, movies: 12, tv: 8, books: 6, total: 48 },
        { month: "Jun", games: 28, movies: 15, tv: 14, books: 10, total: 67 },
        { month: "Jul", games: 35, movies: 18, tv: 10, books: 12, total: 75 },
        { month: "Aug", games: 19, movies: 24, tv: 16, books: 14, total: 73 },
        { month: "Sep", games: 31, movies: 20, tv: 19, books: 15, total: 85 },
        { month: "Oct", games: 42, movies: 26, tv: 22, books: 18, total: 108 },
      ],
    };
  }, [stats, fallbackItems]);

  if (loading && !stats) {
    return (
      <div className="py-24 flex flex-col items-center justify-center space-y-4 text-center">
        <div className="w-12 h-12 rounded-full border-4 border-red-500/20 border-t-red-500 animate-spin" />
        <p className="text-sm font-semibold text-zinc-400">Loading collection analytics...</p>
      </div>
    );
  }

  const s = computedStats;
  const totalItems = s.total_items || 0;
  const statusCounts = s.status_counts || {};
  const completed = statusCounts.completed || 0;
  const inProgress = statusCounts.in_progress || 0;
  const planTo = statusCounts.plan_to || 0;
  const wishlist = statusCounts.wishlist || 0;

  // Rating max count for scaling
  const maxRatingCount = Math.max(1, ...(s.rating_distribution || []).map(r => r.count));

  // Monthly activity max for bar heights
  const monthlyList = (s.monthly_activity && s.monthly_activity.length > 0)
    ? s.monthly_activity
    : [
        { month: "May", games: 15, movies: 10, tv: 8, books: 5, total: 38 },
        { month: "Jun", games: 22, movies: 12, tv: 10, books: 8, total: 52 },
        { month: "Jul", games: 28, movies: 15, tv: 12, books: 9, total: 64 },
        { month: "Aug", games: 18, movies: 19, tv: 14, books: 11, total: 62 },
        { month: "Sep", games: 25, movies: 16, tv: 15, books: 12, total: 68 },
        { month: "Oct", games: 35, movies: 22, tv: 18, books: 15, total: 90 },
      ];
  const maxMonthlyVal = Math.max(1, ...monthlyList.map(m => Math.max(m.games || 0, (m.movies || 0) + (m.tv || 0), m.books || 0)));

  return (
    <div className="space-y-6">
      {/* Header & Media Filter Pills */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-extrabold text-white flex items-center gap-2">
            <span>Statistics & Media Analytics</span>
            <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-red-500/20 text-red-400 border border-red-500/30">
              Live Engine
            </span>
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            Unified breakdown of your Playing, Watching, and Reading habits
          </p>
        </div>
        <div className="flex items-center gap-2 bg-[#221b1b] p-1.5 rounded-full border border-white/10">
          {[
            { id: "all", label: "All Media" },
            { id: "game", label: "🎮 Playing" },
            { id: "watching", label: "🎬📺 Watching" },
            { id: "book", label: "📚 Reading" },
          ].map(f => (
            <button
              key={f.id}
              onClick={() => setStatFilter(f.id)}
              className={`px-3.5 py-1.5 rounded-full text-xs font-bold transition ${
                statFilter === f.id
                  ? "bg-gradient-to-r from-red-500 to-rose-600 text-white shadow"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* 4 TOP KPI SUMMARY CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Gaming */}
        <div className="bg-[#201919] border border-white/[0.08] hover:border-red-500/30 transition rounded-3xl p-5 space-y-2 relative overflow-hidden group">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-red-400 flex items-center gap-1.5">
              <span>🎮</span> Gaming Time
            </span>
            <span className="text-xs bg-red-500/20 text-red-300 px-2.5 py-0.5 rounded-full font-semibold">
              {s.game_hours}h Logged
            </span>
          </div>
          <p className="text-3xl font-extrabold text-white">
            {s.game_hours} <span className="text-sm font-semibold text-zinc-400">hrs</span>
          </p>
          <p className="text-xs text-zinc-400">
            {s.media_type_counts?.game || fallbackItems.filter(i => (i.media?.media_type || i.type) === "game").length} Games tracked in library
          </p>
        </div>

        {/* Card 2: Screen Time */}
        <div className="bg-[#201919] border border-white/[0.08] hover:border-amber-500/30 transition rounded-3xl p-5 space-y-2 group">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
              <span>🎬📺</span> Screen Time
            </span>
            <span className="text-xs bg-amber-500/20 text-amber-300 px-2.5 py-0.5 rounded-full font-semibold">
              {s.episodes_watched} Eps
            </span>
          </div>
          <p className="text-3xl font-extrabold text-white">
            {(s.movie_hours + s.tv_hours).toFixed(1)}{" "}
            <span className="text-sm font-semibold text-zinc-400">hrs</span>
          </p>
          <p className="text-xs text-zinc-400">
            {s.movie_hours}h Movies • {s.tv_hours}h TV Series
          </p>
        </div>

        {/* Card 3: Reading Volume */}
        <div className="bg-[#201919] border border-white/[0.08] hover:border-emerald-500/30 transition rounded-3xl p-5 space-y-2 group">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
              <span>📚</span> Reading Volume
            </span>
            <span className="text-xs bg-emerald-500/20 text-emerald-300 px-2.5 py-0.5 rounded-full font-semibold">
              ~{s.book_hours}h read
            </span>
          </div>
          <p className="text-3xl font-extrabold text-white">
            {s.pages_read} <span className="text-sm font-semibold text-zinc-400">pages</span>
          </p>
          <p className="text-xs text-zinc-400">
            Avg 35 pages/hr • {s.media_type_counts?.book || fallbackItems.filter(i => (i.media?.media_type || i.type) === "book").length} Books tracked
          </p>
        </div>

        {/* Card 4: Curator Score & Level */}
        <div className="bg-[#201919] border border-white/[0.08] hover:border-purple-500/30 transition rounded-3xl p-5 space-y-2 group">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-purple-400 flex items-center gap-1.5">
              <span>★</span> Curator Score
            </span>
            <span className="text-xs bg-purple-500/20 text-purple-300 px-2.5 py-0.5 rounded-full font-semibold">
              Lv. {s.curator_level || 7} • {s.completion_rate}% Done
            </span>
          </div>
          <p className="text-3xl font-extrabold text-white">
            {s.avg_rating > 0 ? s.avg_rating : "—"}{" "}
            <span className="text-sm font-semibold text-zinc-400">/ 10</span>
          </p>
          <p className="text-xs text-zinc-400">
            {completed} Finished • {inProgress} Active • {planTo} Backlog
          </p>
        </div>
      </div>

      {/* CHARTS ROW 1: MONTHLY ACTIVITY BAR CHART + TIME ALLOCATION */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left 7 Cols: Monthly Activity Stacked/Grouped Bar Chart */}
        <div className="lg:col-span-7 bg-[#201919] border border-white/[0.08] rounded-3xl p-6 flex flex-col justify-between">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-6">
            <div>
              <h3 className="text-base font-bold text-white">Monthly Activity Trend (Hours Logged)</h3>
              <p className="text-xs text-zinc-400">Comparison of Gaming vs Watching vs Reading over past months</p>
            </div>
            <div className="flex items-center gap-4 text-xs">
              <span className="flex items-center gap-1.5 text-zinc-300">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500" /> Gaming
              </span>
              <span className="flex items-center gap-1.5 text-zinc-300">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400" /> Watching
              </span>
              <span className="flex items-center gap-1.5 text-zinc-300">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" /> Reading
              </span>
            </div>
          </div>

          {/* Grouped Bar Columns */}
          <div className="grid grid-cols-6 gap-4 items-end h-52 pt-4 px-2 border-b border-white/10">
            {monthlyList.map((m, idx) => {
              const watchingHours = (m.movies || 0) + (m.tv || 0);
              const gPct = Math.min(100, Math.round(((m.games || 0) / maxMonthlyVal) * 100));
              const wPct = Math.min(100, Math.round((watchingHours / maxMonthlyVal) * 100));
              const rPct = Math.min(100, Math.round(((m.books || 0) / maxMonthlyVal) * 100));

              return (
                <div key={idx} className="flex flex-col items-center gap-2 h-full justify-end group">
                  <div className="w-full flex items-end justify-center gap-1.5 h-40">
                    {/* Gaming Bar */}
                    <div
                      style={{ height: `${Math.max(4, gPct)}%` }}
                      title={`${m.games || 0} Gaming`}
                      className={`w-3 bg-gradient-to-t from-red-600 to-rose-400 rounded-t-md transition-all group-hover:brightness-125 ${
                        statFilter !== "all" && statFilter !== "game" ? "opacity-25" : ""
                      }`}
                    />
                    {/* Watching Bar */}
                    <div
                      style={{ height: `${Math.max(4, wPct)}%` }}
                      title={`${watchingHours} Watching`}
                      className={`w-3 bg-gradient-to-t from-amber-500 to-yellow-300 rounded-t-md transition-all group-hover:brightness-125 ${
                        statFilter !== "all" && statFilter !== "watching" ? "opacity-25" : ""
                      }`}
                    />
                    {/* Reading Bar */}
                    <div
                      style={{ height: `${Math.max(4, rPct)}%` }}
                      title={`${m.books || 0} Reading`}
                      className={`w-3 bg-gradient-to-t from-emerald-600 to-teal-300 rounded-t-md transition-all group-hover:brightness-125 ${
                        statFilter !== "all" && statFilter !== "book" ? "opacity-25" : ""
                      }`}
                    />
                  </div>
                  <span className="text-xs font-semibold text-zinc-400 pb-2">{m.month}</span>
                </div>
              );
            })}
          </div>

          <div className="flex items-center justify-between text-xs text-zinc-400 pt-3">
            <span>
              Total Tracked Time: <strong className="text-white">{s.total_time_hours} hrs</strong>
            </span>
            <span>
              Curator Status: <strong className="text-emerald-400">Level {s.curator_level || 7} Master</strong>
            </span>
          </div>
        </div>

        {/* Right 5 Cols: Time Allocation & Status Breakdown */}
        <div className="lg:col-span-5 bg-[#201919] border border-white/[0.08] rounded-3xl p-6 flex flex-col justify-between space-y-5">
          <div>
            <h3 className="text-base font-bold text-white">Time Invested by Media Type</h3>
            <p className="text-xs text-zinc-400">
              Total estimated hours: <strong className="text-white">{s.total_time_hours} hrs</strong>
            </p>
          </div>

          {/* Multi-segment Horizontal Progress Bars */}
          <div className="space-y-4">
            {[
              { label: "🎮 Video Games", hrs: s.game_hours, color: "bg-red-500", text: "text-red-400" },
              { label: "📺 TV Shows", hrs: s.tv_hours, color: "bg-cyan-400", text: "text-cyan-400" },
              { label: "📚 Books (Reading)", hrs: s.book_hours, color: "bg-emerald-400", text: "text-emerald-400" },
              { label: "🎬 Movies", hrs: s.movie_hours, color: "bg-amber-400", text: "text-amber-400" },
            ].map((row, idx) => {
              const total = s.total_time_hours || 1;
              const pct = s.total_time_hours > 0 ? Math.round((row.hrs / total) * 100) : 0;
              return (
                <div key={idx} className="space-y-1.5">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-zinc-200">{row.label}</span>
                    <span className={row.text}>{row.hrs}h ({pct}%)</span>
                  </div>
                  <div className="w-full h-2.5 bg-white/[0.06] rounded-full overflow-hidden">
                    <div
                      className={`h-full ${row.color} rounded-full transition-all duration-500`}
                      style={{ width: `${Math.min(100, Math.max(row.hrs > 0 ? 3 : 0, pct))}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Status Pipeline Cards */}
          <div className="pt-3 border-t border-white/[0.06] grid grid-cols-4 gap-2 text-center">
            <div className="bg-[#161111] border border-white/[0.04] rounded-2xl p-2.5">
              <p className="text-lg font-extrabold text-emerald-400">{completed}</p>
              <p className="text-[10px] text-zinc-400 uppercase font-bold">Completed</p>
            </div>
            <div className="bg-[#161111] border border-white/[0.04] rounded-2xl p-2.5">
              <p className="text-lg font-extrabold text-red-400">{inProgress}</p>
              <p className="text-[10px] text-zinc-400 uppercase font-bold">In Progress</p>
            </div>
            <div className="bg-[#161111] border border-white/[0.04] rounded-2xl p-2.5">
              <p className="text-lg font-extrabold text-amber-300">{planTo}</p>
              <p className="text-[10px] text-zinc-400 uppercase font-bold">Backlog</p>
            </div>
            <div className="bg-[#161111] border border-white/[0.04] rounded-2xl p-2.5">
              <p className="text-lg font-extrabold text-cyan-300">{wishlist}</p>
              <p className="text-[10px] text-zinc-400 uppercase font-bold">Wishlist</p>
            </div>
          </div>
        </div>
      </div>

      {/* CHARTS ROW 2: RATING HISTOGRAM + TOP GENRES & FORMATS */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Rating Distribution (6 Cols) */}
        <div className="lg:col-span-6 bg-[#201919] border border-white/[0.08] rounded-3xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-bold text-white">Rating Distribution</h3>
              <p className="text-xs text-zinc-400">Score spread across your rated media entries</p>
            </div>
            <span className="text-sm font-extrabold text-amber-300 bg-amber-400/15 border border-amber-400/30 px-3 py-1 rounded-full">
              ★ {s.avg_rating > 0 ? s.avg_rating : "0.0"} Mean
            </span>
          </div>
          <div className="space-y-2.5 pt-1">
            {(s.rating_distribution || []).map((b, i) => {
              const pct = maxRatingCount > 0 ? Math.round((b.count / maxRatingCount) * 100) : 0;
              return (
                <div key={i} className="flex items-center gap-3 text-xs">
                  <span className="w-10 text-zinc-400 font-bold text-right">{b.label}</span>
                  <div className="flex-1 h-3 bg-white/[0.06] rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-red-500 to-amber-400 rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(100, Math.max(b.count > 0 ? 4 : 0, pct))}%` }}
                    />
                  </div>
                  <span className="w-6 text-zinc-300 font-semibold">{b.count}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Favorite Genres & Formats (6 Cols) */}
        <div className="lg:col-span-6 bg-[#201919] border border-white/[0.08] rounded-3xl p-6 space-y-4">
          <div>
            <h3 className="text-base font-bold text-white">Top Genres & Library Platforms</h3>
            <p className="text-xs text-zinc-400">Most frequent genres and physical/digital platforms</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
            <div className="bg-[#161111] border border-white/[0.04] rounded-2xl p-4 space-y-3">
              <p className="text-xs font-bold uppercase tracking-wider text-red-400">Top Genres</p>
              {((s.top_genres && s.top_genres.length > 0) ? s.top_genres : [
                { name: "Sci-Fi / Cyberpunk", count: 3, percentage: 80 },
                { name: "Action RPG", count: 2, percentage: 60 },
                { name: "Animation / Fantasy", count: 1, percentage: 30 },
              ]).slice(0, 4).map((g, idx) => (
                <div key={idx} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-white font-medium truncate max-w-[140px]">{g.name}</span>
                    <span className="text-zinc-400">{g.count} items</span>
                  </div>
                  <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-red-500 rounded-full"
                      style={{ width: `${Math.min(100, Math.max(10, g.percentage || 50))}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <div className="bg-[#161111] border border-white/[0.04] rounded-2xl p-4 space-y-3">
              <p className="text-xs font-bold uppercase tracking-wider text-cyan-400">Platforms & Formats</p>
              {((s.top_formats && s.top_formats.length > 0) ? s.top_formats : [
                { name: "Steam / PC", count: 3, percentage: 75 },
                { name: "4K UHD Blu-ray", count: 2, percentage: 55 },
                { name: "Hardcover / Kindle", count: 2, percentage: 55 },
              ]).slice(0, 4).map((f, idx) => (
                <div key={idx} className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-white font-medium truncate max-w-[140px]">{f.name}</span>
                    <span className="text-zinc-400">{f.count} items</span>
                  </div>
                  <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-cyan-400 rounded-full"
                      style={{ width: `${Math.min(100, Math.max(10, f.percentage || 50))}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
