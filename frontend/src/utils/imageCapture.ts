/**
 * Utility functions for image capture and compression in reporting features
 */

export interface ImageCaptureResult {
  dataUrl: string
  blob: Blob
  size: number
  width: number
  height: number
}

/**
 * Convert a File or Blob to a data URL
 */
export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = () => reject(new Error("Failed to read file"))
    reader.readAsDataURL(file)
  })
}

/**
 * Compress and resize an image file
 */
export async function compressImage(
  file: File,
  maxWidth: number = 2048,
  maxHeight: number = 2048,
  quality: number = 0.8
): Promise<ImageCaptureResult> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => {
      try {
        // Calculate new dimensions
        let { width, height } = img

        if (width > height) {
          if (width > maxWidth) {
            height = (height * maxWidth) / width
            width = maxWidth
          }
        } else {
          if (height > maxHeight) {
            width = (width * maxHeight) / height
            height = maxHeight
          }
        }

        // Create canvas and draw resized image
        const canvas = document.createElement("canvas")
        canvas.width = width
        canvas.height = height

        const ctx = canvas.getContext("2d")
        if (!ctx) {
          reject(new Error("Failed to get canvas context"))
          return
        }

        ctx.drawImage(img, 0, 0, width, height)

        // Convert to blob
        canvas.toBlob(
          (blob) => {
            if (!blob) {
              reject(new Error("Failed to create blob"))
              return
            }

            const dataUrl = canvas.toDataURL("image/jpeg", quality)
            resolve({
              dataUrl,
              blob,
              size: blob.size,
              width,
              height,
            })
          },
          "image/jpeg",
          quality
        )
      } catch (error) {
        reject(error)
      }
    }

    img.onerror = () => reject(new Error("Failed to load image"))
    img.src = URL.createObjectURL(file)
  })
}

/**
 * Capture image from device camera or file input
 */
export function captureImage(
  options: {
    preferCamera?: boolean
    maxWidth?: number
    maxHeight?: number
    quality?: number
  } = {}
): Promise<ImageCaptureResult> {
  return new Promise((resolve, reject) => {
    const input = document.createElement("input")
    input.type = "file"
    input.accept = "image/*"

    if (options.preferCamera) {
      input.capture = "environment" // Use rear camera on mobile
    }

    input.onchange = async (event) => {
      const file = (event.target as HTMLInputElement).files?.[0]
      if (!file) {
        reject(new Error("No file selected"))
        return
      }

      try {
        const result = await compressImage(
          file,
          options.maxWidth,
          options.maxHeight,
          options.quality
        )
        resolve(result)
      } catch (error) {
        reject(error)
      }
    }

    input.click()
  })
}

/**
 * Get user's current GPS location
 */
export function getCurrentLocation(): Promise<{
  lat: number
  lng: number
  accuracy: number
}> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation is not supported by this browser"))
      return
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          accuracy: position.coords.accuracy,
        })
      },
      (error) => {
        let message = "Failed to get location"
        switch (error.code) {
          case error.PERMISSION_DENIED:
            message = "Location access denied by user"
            break
          case error.POSITION_UNAVAILABLE:
            message = "Location information unavailable"
            break
          case error.TIMEOUT:
            message = "Location request timed out"
            break
        }
        reject(new Error(message))
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 300000, // 5 minutes
      }
    )
  })
}

/**
 * Check if the device supports camera capture
 */
export function supportsCameraCapture(): boolean {
  const input = document.createElement("input")
  input.type = "file"
  input.accept = "image/*"

  // Check if capture attribute is supported
  return (
    "capture" in input &&
    !!navigator.mediaDevices &&
    !!navigator.mediaDevices.getUserMedia
  )
}
