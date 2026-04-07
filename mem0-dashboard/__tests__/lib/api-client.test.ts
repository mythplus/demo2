/**
 * API 客户端测试 - 覆盖 mem0Api 核心方法
 */

const mockFetch = global.fetch as jest.Mock;

// 每个测试前重置 fetch mock
beforeEach(() => {
  mockFetch.mockReset();
});

// 辅助函数：模拟成功的 JSON 响应
function mockJsonResponse(data: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    text: () => Promise.resolve(JSON.stringify(data)),
    json: () => Promise.resolve(data),
  });
}

// 辅助函数：模拟失败的响应
function mockErrorResponse(detail: string, status = 500) {
  return Promise.resolve({
    ok: false,
    status,
    statusText: "Internal Server Error",
    text: () => Promise.resolve(JSON.stringify({ detail })),
    json: () => Promise.resolve({ detail }),
  });
}

// 辅助函数：模拟空响应（DELETE 场景）
function mockEmptyResponse() {
  return Promise.resolve({
    ok: true,
    status: 204,
    statusText: "No Content",
    text: () => Promise.resolve(""),
    json: () => Promise.reject(new Error("No content")),
  });
}

describe("mem0Api", () => {
  let mem0Api: typeof import("@/lib/api/client").mem0Api;

  beforeEach(async () => {
    jest.resetModules();
    const mod = await import("@/lib/api/client");
    mem0Api = mod.mem0Api;
  });

  // ============ healthCheck ============

  describe("healthCheck", () => {
    it("连接成功时应返回 true", async () => {
      mockFetch.mockReturnValueOnce(
        Promise.resolve({ ok: true })
      );
      const result = await mem0Api.healthCheck();
      expect(result).toBe(true);
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    it("连接失败时应返回 false", async () => {
      mockFetch.mockReturnValueOnce(
        Promise.resolve({ ok: false })
      );
      const result = await mem0Api.healthCheck();
      expect(result).toBe(false);
    });

    it("网络异常时应返回 false", async () => {
      mockFetch.mockRejectedValueOnce(new Error("Network error"));
      const result = await mem0Api.healthCheck();
      expect(result).toBe(false);
    });
  });

  // ============ getMemories ============

  describe("getMemories", () => {
    const mockMemories = [
      { id: "1", memory: "测试记忆1", user_id: "user1", state: "active" },
      { id: "2", memory: "测试记忆2", user_id: "user2", state: "active" },
    ];

    it("无筛选参数时应请求 /v1/memories/", async () => {
      mockFetch.mockReturnValueOnce(mockJsonResponse(mockMemories));
      const result = await mem0Api.getMemories();
      expect(result).toEqual(mockMemories);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/v1/memories/"),
        expect.objectContaining({ signal: expect.any(Object) })
      );
    });

    it("传入字符串 userId 时应拼接 user_id 参数", async () => {
      mockFetch.mockReturnValueOnce(mockJsonResponse(mockMemories));
      await mem0Api.getMemories("user1");
      const url = mockFetch.mock.calls[0][0] as string;
      expect(url).toContain("user_id=user1");
    });

    it("传入 FilterParams 对象时应正确拼接查询参数", async () => {
      mockFetch.mockReturnValueOnce(mockJsonResponse(mockMemories));
      await mem0Api.getMemories({
        user_id: "user1",
        state: "active",
        categories: ["work", "health"],
      });
      const url = mockFetch.mock.calls[0][0] as string;
      expect(url).toContain("user_id=user1");
      expect(url).toContain("state=active");
      expect(url).toContain("categories=work%2Chealth");
    });

    it("请求失败时应抛出错误", async () => {
      mockFetch.mockReturnValueOnce(mockErrorResponse("服务器错误"));
      await expect(mem0Api.getMemories()).rejects.toThrow("服务器错误");
    });
  });

  // ============ getMemory ============

  describe("getMemory", () => {
    it("应请求正确的 URL", async () => {
      const mockMemory = { id: "abc-123", memory: "测试", state: "active" };
      mockFetch.mockReturnValueOnce(mockJsonResponse(mockMemory));
      const result = await mem0Api.getMemory("abc-123");
      expect(result).toEqual(mockMemory);
      const url = mockFetch.mock.calls[0][0] as string;
      expect(url).toContain("/v1/memories/abc-123/");
    });
  });

  // ============ addMemory ============

  describe("addMemory", () => {
    it("应发送 POST 请求并携带正确的 body", async () => {
      const mockResponse = {
        results: [{ id: "new-1", memory: "新记忆", event: "ADD" }],
      };
      mockFetch.mockReturnValueOnce(mockJsonResponse(mockResponse));

      const result = await mem0Api.addMemory({
        messages: [{ role: "user", content: "我喜欢蓝色" }],
        user_id: "user1",
      });

      expect(result).toEqual(mockResponse);
      const [, options] = mockFetch.mock.calls[0];
      expect(options.method).toBe("POST");
      const body = JSON.parse(options.body);
      expect(body.messages[0].content).toBe("我喜欢蓝色");
      expect(body.user_id).toBe("user1");
    });
  });

  // ============ updateMemory ============

  describe("updateMemory", () => {
    it("应发送 PUT 请求", async () => {
      const mockUpdated = { id: "1", memory: "更新后的内容", state: "active" };
      mockFetch.mockReturnValueOnce(mockJsonResponse(mockUpdated));

      const result = await mem0Api.updateMemory("1", { text: "更新后的内容" });
      expect(result).toEqual(mockUpdated);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toContain("/v1/memories/1/");
      expect(options.method).toBe("PUT");
    });
  });

  // ============ deleteMemory ============

  describe("deleteMemory", () => {
    it("应发送 DELETE 请求", async () => {
      mockFetch.mockReturnValueOnce(mockEmptyResponse());
      const result = await mem0Api.deleteMemory("1");
      expect(result).toEqual({});
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toContain("/v1/memories/1/");
      expect(options.method).toBe("DELETE");
    });
  });

  // ============ batchDeleteMemories ============

  describe("batchDeleteMemories", () => {
    it("应发送 POST 请求到 batch-delete 端点", async () => {
      const mockResponse = { total: 3, success: 3, failed: 0, results: [] };
      mockFetch.mockReturnValueOnce(mockJsonResponse(mockResponse));

      const result = await mem0Api.batchDeleteMemories(["1", "2", "3"]);
      expect(result.total).toBe(3);
      expect(result.success).toBe(3);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toContain("/v1/memories/batch-delete");
      expect(options.method).toBe("POST");
      const body = JSON.parse(options.body);
      expect(body.memory_ids).toEqual(["1", "2", "3"]);
    });
  });

  // ============ searchMemories ============

  describe("searchMemories", () => {
    it("应发送 POST 请求并返回搜索结果", async () => {
      const mockResponse = {
        results: [
          { id: "1", memory: "蓝色是最喜欢的颜色", score: 0.95, state: "active" },
        ],
      };
      mockFetch.mockReturnValueOnce(mockJsonResponse(mockResponse));

      const result = await mem0Api.searchMemories({
        query: "喜欢什么颜色",
        user_id: "user1",
        limit: 5,
      });

      expect(result.results).toHaveLength(1);
      expect(result.results[0].score).toBe(0.95);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toContain("/v1/memories/search/");
      expect(options.method).toBe("POST");
    });
  });

  // ============ getStats ============

  describe("getStats", () => {
    it("应返回统计数据", async () => {
      const mockStats = {
        total_memories: 100,
        total_users: 10,
        category_distribution: { work: 30, health: 20 },
        state_distribution: { active: 80, paused: 15, deleted: 5 },
        daily_trend: [{ date: "2026-04-07", count: 5 }],
      };
      mockFetch.mockReturnValueOnce(mockJsonResponse(mockStats));

      const result = await mem0Api.getStats();
      expect(result.total_memories).toBe(100);
      expect(result.total_users).toBe(10);
    });
  });

  // ============ getMemoryHistory ============

  describe("getMemoryHistory", () => {
    it("应请求正确的历史记录 URL", async () => {
      const mockHistory = [
        { id: "h1", memory_id: "1", new_memory: "内容", event: "ADD", created_at: "2026-01-01" },
      ];
      mockFetch.mockReturnValueOnce(mockJsonResponse(mockHistory));

      const result = await mem0Api.getMemoryHistory("1");
      expect(result).toHaveLength(1);
      const url = mockFetch.mock.calls[0][0] as string;
      expect(url).toContain("/v1/memories/history/1/");
    });
  });

  // ============ 错误处理 ============

  describe("错误处理", () => {
    it("HTTP 错误应抛出包含 detail 的错误信息", async () => {
      mockFetch.mockReturnValueOnce(mockErrorResponse("记忆不存在", 404));
      await expect(mem0Api.getMemory("not-exist")).rejects.toThrow("记忆不存在");
    });

    it("JSON 解析失败时应使用 HTTP 状态码作为错误信息", async () => {
      mockFetch.mockReturnValueOnce(
        Promise.resolve({
          ok: false,
          status: 502,
          statusText: "Bad Gateway",
          text: () => Promise.resolve("not json"),
          json: () => Promise.reject(new Error("parse error")),
        })
      );
      await expect(mem0Api.getMemory("1")).rejects.toThrow("HTTP 502");
    });
  });
});
