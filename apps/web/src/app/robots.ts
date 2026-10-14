import { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL || "https://clipitup.example.com";

  return {
    rules: {
      userAgent: "*",
      allow: ["/", "/terms", "/privacy", "/aup", "/refund", "/copyright", "/subprocessors"],
      disallow: ["/admin", "/api/", "/review/"],
    },
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}
