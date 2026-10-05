import { create } from "zustand";
import { Video, Job } from "@clip-it-up/shared";

interface AppState {
  isUploadModalOpen: boolean;
  activeUploadProgress: number | null;
  activeUploadFilename: string | null;
  videos: Video[];
  recentJobs: Record<string, Job>;
  setUploadModalOpen: (open: boolean) => void;
  setActiveUploadProgress: (progress: number | null, filename?: string | null) => void;
  setVideos: (videos: Video[]) => void;
  updateJob: (job: Job) => void;
}

export const useAppStore = create<AppState>((set) => ({
  isUploadModalOpen: false,
  activeUploadProgress: null,
  activeUploadFilename: null,
  videos: [],
  recentJobs: {},
  setUploadModalOpen: (open) => set({ isUploadModalOpen: open }),
  setActiveUploadProgress: (progress, filename) =>
    set((state) => ({
      activeUploadProgress: progress,
      activeUploadFilename: filename !== undefined ? filename : state.activeUploadFilename,
    })),
  setVideos: (videos) => set({ videos }),
  updateJob: (job) =>
    set((state) => ({
      recentJobs: { ...state.recentJobs, [job.id]: job },
    })),
}));
