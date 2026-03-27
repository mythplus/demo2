"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, Link2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CategoryBadges } from "@/components/memories/category-badge";
import { mem0Api } from "@/lib/api";
import type { RelatedMemory } from "@/lib/api";

interface RelatedMemoriesProps {
  memoryId: string;
  className?: string;
}

export function RelatedMemories({ memoryId, className }: RelatedMemoriesProps) {
  const [related, setRelated] = useState<RelatedMemory[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    mem0Api
      .getRelatedMemories(memoryId, 5)
      .then((res) => {
        if (!cancelled) {
          setRelated(res.results || []);
        }
      })
      .catch(() => {
        if (!cancelled) setRelated([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [memoryId]);

  // 相似度颜色
  const getScoreColor = (score: number) => {
    if (score >= 0.8) return "text-green-600 dark:text-green-400";
    if (score >= 0.6) return "text-yellow-600 dark:text-yellow-400";
    return "text-orange-600 dark:text-orange-400";
  };

  const getScoreBg = (score: number) => {
    if (score >= 0.8) return "bg-green-100 dark:bg-green-900/30";
    if (score >= 0.6) return "bg-yellow-100 dark:bg-yellow-900/30";
    return "bg-orange-100 dark:bg-orange-900/30";
  };

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Link2 className="h-4 w-4" />
          关联记忆
        </CardTitle>
        <CardDescription>语义相关的记忆推荐</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : related.length > 0 ? (
          <div className="space-y-2">
            {related.map((item) => (
              <Link
                key={item.id}
                href={`/memory/${item.id}`}
                className="flex items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-accent/50"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm line-clamp-2 leading-relaxed">
                    {item.memory}
                  </p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    {item.user_id && (
                      <Badge variant="secondary" className="text-xs">
                        {item.user_id}
                      </Badge>
                    )}
                    <CategoryBadges categories={item.categories} max={2} />
                  </div>
                </div>
                {/* 相似度 */}
                {item.score !== undefined && (
                  <div className={`shrink-0 rounded-md px-2 py-1 text-center ${getScoreBg(item.score)}`}>
                    <p className={`text-sm font-bold ${getScoreColor(item.score)}`}>
                      {(item.score * 100).toFixed(0)}%
                    </p>
                  </div>
                )}
              </Link>
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <Link2 className="mb-3 h-8 w-8 text-muted-foreground/30" />
            <p className="text-sm text-muted-foreground">暂无关联记忆</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
