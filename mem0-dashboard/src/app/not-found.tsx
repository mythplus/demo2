import { FileQuestion, Home, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <Card className="w-full max-w-md">
        <CardContent className="flex flex-col items-center gap-4 pt-8 pb-6 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
            <FileQuestion className="h-8 w-8 text-muted-foreground" />
          </div>
          <div className="space-y-2">
            <h2 className="text-xl font-semibold">页面不存在</h2>
            <p className="text-sm text-muted-foreground">
              您访问的页面不存在或已被移除，请检查 URL 是否正确。
            </p>
          </div>
          <div className="flex gap-3 mt-2">
            <Link href="/">
              <Button variant="outline">
                <Home className="mr-2 h-4 w-4" />
                返回首页
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
