import os
import time
import json
import csv
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2
from scipy.ndimage import gaussian_filter
from scipy.signal import find_peaks
import matplotlib.pyplot as plt
from argparse import ArgumentParser

os.environ["CUDA_VISIBLE_DEVICES"] = "4"


def video2jpg(video_path, output_folder, sample_freq=1):
    os.makedirs(output_folder, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Error: Could not open video.")
        return
    frame_index = 0
    save_index = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_index % sample_freq == 0:
            frame_filename = os.path.join(output_folder, f"{save_index:04d}.jpg")
            cv2.imwrite(frame_filename, frame)
            save_index += 1
        frame_index += 1
    cap.release()
    print(f"All frames have been saved to {output_folder}.")


class FrameExtractor:
    def __init__(self, video_path, output_dir, gaussian_sigma=5, prominence=0.8, csv_file='new_wooden_block_selected_valleys.csv'):
        self._folder_init(video_path, output_dir)
        self._mediapipe_init()
        self._visualization_init()
        self.cap = cv2.VideoCapture(self.video_path)
        self.num_frame = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.all_landmark_pos = {"Right": np.full((self.num_frame, 2), np.nan), "Left": np.full((self.num_frame, 2), np.nan)}
        self.gaussian_sigma = gaussian_sigma
        self.prominence = prominence
        self.csv_file = csv_file

    def extract_frames(self):
        self.analyze_video()
        self.all_possible_handedness = set(self.all_landmark_pos.keys())
        self.all_speeds = {}
        all_selected_valleys = []
        for handedness in self.all_possible_handedness:
            coords = self.all_landmark_pos[handedness]
            speed = self.get_speed(coords)
            self.all_speeds[handedness] = speed
            if np.all(np.isnan(speed)):
                continue
            smoothed_curve = self.process_speed_curve_for(handedness)
            _, valleys = self.get_peaks_valleys(smoothed_curve, handedness)
            selected_valleys = []
            for i in range(len(valleys)):
                if i == 0 or (valleys[i] - selected_valleys[-1]) >= 15:
                    selected_valleys.append(valleys[i])
            
            all_selected_valleys.extend((valley, handedness) for valley in selected_valleys)
        all_selected_valleys = sorted(all_selected_valleys, key=lambda x: x[0])
        final_valley_list = [int(i[0]) for i in all_selected_valleys]
        final_valley_list.insert(0, 0)
        final_valley_list.append(self.num_frame - 1)
        with open(self.base_folder / 'keyframelist.json', 'w', encoding='utf-8') as f:
            json.dump(final_valley_list, f, ensure_ascii=False, indent=4)
        for idx in final_valley_list:
            frame = self.get_frame(idx)
            cv2.imwrite(f'{str(self.selected_folder)}/{idx}.jpg', frame)
        self.cap.release()
        video2jpg(video_path=self.video_path, output_folder=str(self.frames_folder), sample_freq=1)
        print("Done.")

    def analyze_video(self):
        self.hand_detected_frames = []
        frame_counter = 0
        BaseOptions = mp.tasks.BaseOptions
        HandLandmarker = mp.tasks.vision.HandLandmarker
        HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
        VisionRunningMode = mp.tasks.vision.RunningMode
        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path='./hand_landmarker.task'),
            running_mode=VisionRunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.2,
            min_hand_presence_confidence=0.2,
            min_tracking_confidence=0.2,
        )
        with HandLandmarker.create_from_options(options) as landmarker:
            while self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    break
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
                mp_timestamp = int(round(time.time() * 1000))
                results = landmarker.detect_for_video(mp_image, mp_timestamp)
                annotated_image, avg_landmark_x, avg_landmark_y, all_handedness = self.process_frame_results(rgb_image=frame, detection_result=results)
                if len(all_handedness) == 0:
                    self.all_landmark_pos['Right'][frame_counter] = np.array([np.nan, np.nan])
                    self.all_landmark_pos['Left'][frame_counter] = np.array([np.nan, np.nan])
                else:
                    for handedness in all_handedness:
                        self.all_landmark_pos[handedness][frame_counter] = (avg_landmark_x[handedness], avg_landmark_y[handedness])
                    self.hand_detected_frames.append(frame_counter)
                cv2.imwrite(f'{str(self.hand_images_folder)}/{frame_counter}.jpg', annotated_image)
                frame_counter += 1
        with open(self.base_folder / 'frames_with_hand.json', 'w', encoding='utf-8') as f:
            json.dump(self.hand_detected_frames, f, indent=4)

    def process_frame_results(self, rgb_image, detection_result):
        hand_landmarks_list = detection_result.hand_landmarks
        handedness_list = detection_result.handedness
        annotated_image = np.copy(rgb_image)
        avg_landmark_x = {}
        avg_landmark_y = {}
        all_handedness = set()
        for idx in range(len(hand_landmarks_list)):
            hand_landmarks = hand_landmarks_list[idx]
            handedness = handedness_list[idx]
            hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
            hand_landmarks_proto.landmark.extend([
                landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) for landmark in hand_landmarks
            ])
            solutions.drawing_utils.draw_landmarks(
                annotated_image,
                hand_landmarks_proto,
                solutions.hands.HAND_CONNECTIONS,
                solutions.drawing_styles.get_default_hand_landmarks_style(),
                solutions.drawing_styles.get_default_hand_connections_style()
            )
            height, width, _ = annotated_image.shape
            x_coordinates = [landmark.x for landmark in hand_landmarks]
            y_coordinates = [landmark.y for landmark in hand_landmarks]
            text_x = int(min(x_coordinates) * width)
            text_y = int(min(y_coordinates) * height) - self.MARGIN
            avg_landmark_x[handedness[0].category_name] = np.average(x_coordinates) * width
            avg_landmark_y[handedness[0].category_name] = np.average(y_coordinates) * height
            all_handedness.add(handedness[0].category_name)
            cv2.putText(annotated_image, f"{handedness[0].category_name}", (text_x, text_y), cv2.FONT_HERSHEY_DUPLEX, self.FONT_SIZE, self.HANDEDNESS_TEXT_COLOR, self.FONT_THICKNESS, cv2.LINE_AA)
        return annotated_image, avg_landmark_x, avg_landmark_y, all_handedness

    def process_speed_curve_for(self, handedness):
        y = self.all_speeds[handedness]
        if np.all(np.isnan(y)):
            return np.zeros_like(y)
        nans = np.isnan(y)
        x = np.arange(len(y))
        y_interpolated = y.copy()
        y_interpolated[nans] = np.interp(x[nans], x[~nans], y[~nans])
        return gaussian_filter(y_interpolated, sigma=self.gaussian_sigma)

    def save_selected_valleys_to_csv(self, selected_valleys, handedness):
        with open(self.csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([self.video_name, handedness, selected_valleys])

    def get_peaks_valleys(self, smoothed_curve, handedness):
        peaks, _ = find_peaks(smoothed_curve)
        valleys, _ = find_peaks(-smoothed_curve)
        x = np.arange(len(smoothed_curve))
        plt.figure()
        plt.plot(x, smoothed_curve, label='Smoothed Data')
        plt.plot(x[peaks], smoothed_curve[peaks], 'rx', label='Peaks')
        plt.plot(x[valleys], smoothed_curve[valleys], 'go', label='Valleys')
        plt.title(f'Smoothed {handedness} Hand Speed Peaks and Valleys')
        plt.savefig(f'{str(self.base_folder)}/{handedness}_speed_smoothed.jpg')
        plt.close()
        return peaks, valleys

    def get_frame(self, frame_number):
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = self.cap.read()
        if not ret:
            return np.zeros((self.VIDEO_HEIGHT, self.VIDEO_WIDTH, 3))
        return frame

    def get_speed(self, coordinates):
        length = len(coordinates)
        speed = np.full(length - 1, np.nan, dtype=float)
        for i in range(length - 1):
            if (not np.any(np.isnan(coordinates[i]))) and (not np.any(np.isnan(coordinates[i + 1]))):
                speed[i] = np.linalg.norm(coordinates[i] - coordinates[i + 1])
        return speed

    def _mediapipe_init(self):
        BaseOptions = mp.tasks.BaseOptions
        self.HandLandmarker = mp.tasks.vision.HandLandmarker
        HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
        VisionRunningMode = mp.tasks.vision.RunningMode
        self.mp_hand_options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path='./hand_landmarker.task'),
            running_mode=VisionRunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.2,
            min_hand_presence_confidence=0.2,
            min_tracking_confidence=0.2,
        )

    def _visualization_init(self):
        self.MARGIN = 10
        self.FONT_SIZE = 1
        self.FONT_THICKNESS = 1
        self.HANDEDNESS_TEXT_COLOR = (88, 205, 54)
        self.VIDEO_WIDTH = 640
        self.VIDEO_HEIGHT = 480

    def _folder_init(self, video_path, output_dir):
        output_dir = Path(output_dir)
        self.video_path = video_path
        self.video_name = Path(video_path).stem

        # 根输出目录：.../<视频名去扩展>/
        self.base_folder = output_dir / self.video_name
        self.base_folder.mkdir(parents=True, exist_ok=True)

        # 仅保留需要的三个子目录
        self.hand_images_folder = self.base_folder / 'hand_images'
        self.hand_images_folder.mkdir(parents=True, exist_ok=True)

        self.selected_folder = self.base_folder / 'selected_frames'
        self.selected_folder.mkdir(parents=True, exist_ok=True)

        self.frames_folder = self.base_folder / 'frames'
        self.frames_folder.mkdir(parents=True, exist_ok=True)

        # 不再创建下列两个目录（按你的需求移除）
        # self.plot_folder = self.base_folder / 'plots'
        # self.all_valleys_folder = self.base_folder / 'all_valleys'



def main(args):
    args_parsed = args.parse_args()
    video_path = args_parsed.video_path
    output_dir = args_parsed.output_dir
    gaussian_sigma = args_parsed.gaussian_sigma
    prominence = args_parsed.prominence
    frame_extractor = FrameExtractor(video_path, output_dir, gaussian_sigma, prominence)
    frame_extractor.extract_frames()


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--video_path', type=str, required=True)
    parser.add_argument('--output_dir', type=str, default='./output')
    parser.add_argument('--gaussian_sigma', type=int, default=5)
    parser.add_argument('--prominence', type=float, default=0.8)
    main(parser)
