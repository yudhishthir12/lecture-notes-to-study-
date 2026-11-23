"use client";

import * as React from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";
import {
  UploadCloud,
  FileText,
  FileCheck2,
  AlertCircle,
  X,
  Loader2,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { formatFileSize } from "@/lib/utils";
import { Document } from "@/types";
import { useRouter } from "next/navigation";

interface UploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUploadSuccess?: (doc: Document) => void;
}

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
const ACCEPTED_TYPES = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": [
    ".pptx",
  ],
  "text/plain": [".txt"],
};

export function UploadDialog({
  open,
  onOpenChange,
  onUploadSuccess,
}: UploadDialogProps) {
  const router = useRouter();
  const [selectedFile, setSelectedFile] = React.useState<File | null>(null);
  const [isUploading, setIsUploading] = React.useState(false);
  const [uploadProgress, setUploadProgress] = React.useState(0);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);

  const resetState = () => {
    setSelectedFile(null);
    setIsUploading(false);
    setUploadProgress(0);
    setErrorMessage(null);
  };

  const onDrop = React.useCallback(
    (acceptedFiles: File[], fileRejections: any[]) => {
      setErrorMessage(null);
      if (fileRejections.length > 0) {
        const rejection = fileRejections[0];
        if (rejection.errors[0]?.code === "file-too-large") {
          setErrorMessage("File size exceeds the 50MB limit.");
        } else {
          setErrorMessage(
            "Invalid file type. Supported formats are PDF (.pdf), PPTX (.pptx), and TXT (.txt).",
          );
        }
        return;
      }
      if (acceptedFiles.length > 0) {
        setSelectedFile(acceptedFiles[0]);
      }
    },
    [],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_FILE_SIZE,
    multiple: false,
    disabled: isUploading,
  });

  const handleUpload = async () => {
    if (!selectedFile) return;

    try {
      setIsUploading(true);
      setErrorMessage(null);
      setUploadProgress(10);

      const uploadedDoc = await api.uploadDocument(selectedFile, (percent) => {
        setUploadProgress(Math.min(percent, 95));
      });

      setUploadProgress(100);
      toast.success("Document uploaded successfully!", {
        description: `Ready for processing: ${uploadedDoc.filename}`,
      });

      onUploadSuccess?.(uploadedDoc);
      onOpenChange(false);
      resetState();

      // Navigate to the uploaded document page
      router.push(`/documents/${uploadedDoc.id}`);
      router.refresh();
    } catch (err: any) {
      console.error("Upload failed:", err);
      const msg =
        err.detail || err.message || "An error occurred during upload.";
      setErrorMessage(msg);
      toast.error("Upload failed", { description: msg });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(val) => {
        if (!isUploading) {
          onOpenChange(val);
          if (!val) resetState();
        }
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <UploadCloud className="h-5 w-5 text-primary" />
            Upload Lecture Notes
          </DialogTitle>
          <DialogDescription>
            Upload your PDF textbook chapters, PPTX slide decks, or TXT lecture
            notes (up to 50MB).
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Dropzone Area */}
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-200 flex flex-col items-center justify-center gap-3 ${
              isDragActive
                ? "border-primary bg-primary/5 scale-[0.99]"
                : "border-muted-foreground/25 hover:border-primary/60 hover:bg-muted/40"
            } ${isUploading ? "pointer-events-none opacity-60" : ""}`}
          >
            <input {...getInputProps()} />
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              <UploadCloud className="h-6 w-6" />
            </div>

            <div className="space-y-1">
              <p className="text-sm font-semibold text-foreground">
                {isDragActive
                  ? "Drop your lecture file here"
                  : "Click to browse or drag & drop"}
              </p>
              <p className="text-xs text-muted-foreground">
                Supported: PDF (.pdf), PowerPoint (.pptx), Text (.txt)
              </p>
            </div>
          </div>

          {/* Selected File Card */}
          {selectedFile && (
            <div className="flex items-center justify-between rounded-lg border bg-muted/30 p-3 text-sm">
              <div className="flex items-center gap-3 min-w-0">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded bg-primary/10 text-primary">
                  <FileText className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-foreground">
                    {selectedFile.name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatFileSize(selectedFile.size)}
                  </p>
                </div>
              </div>

              {!isUploading && (
                <button
                  type="button"
                  onClick={() => setSelectedFile(null)}
                  className="rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          )}

          {/* Upload Progress Bar */}
          {isUploading && (
            <div className="space-y-1.5">
              <div className="flex justify-between text-xs font-medium text-muted-foreground">
                <span>Uploading...</span>
                <span>{uploadProgress}%</span>
              </div>
              <Progress value={uploadProgress} />
            </div>
          )}

          {/* Error Message Box */}
          {errorMessage && (
            <div className="flex items-start gap-2.5 rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-xs text-destructive">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            type="button"
            variant="outline"
            disabled={isUploading}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            disabled={!selectedFile || isUploading}
            onClick={handleUpload}
            className="gap-2"
          >
            {isUploading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Uploading...</span>
              </>
            ) : (
              <>
                <FileCheck2 className="h-4 w-4" />
                <span>Submit & Process</span>
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
