import cv2
import numpy as np
from PIL import Image
import onnxruntime as ort
from utils import load_toml_as_dict


def numpy_nms(boxes, scores, iou_threshold=0.6):
    """Pure-numpy Non-Maximum Suppression.
    boxes: (N, 4) as x1,y1,x2,y2
    scores: (N,)
    Returns: indices of kept boxes."""
    if len(boxes) == 0:
        return np.array([], dtype=int)

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)

    order = scores.argsort()[::-1]
    keep = []

    while len(order) > 0:
        i = order[0]
        keep.append(i)
        if len(order) == 1:
            break

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter)

        inds = np.where(iou <= iou_threshold)[0]
        order = order[inds + 1]

    return np.array(keep, dtype=int)


def numpy_non_max_suppression(prediction, conf_thres=0.6, iou_thres=0.6):
    """Non-max suppression.
    prediction: (batch, num_boxes, 4+1+num_classes) or (batch, 4+1+num_classes, num_boxes)
    Returns: list of (N, 6) arrays [x1, y1, x2, y2, conf, cls] per batch."""
    output = []

    # Handle both (batch, boxes, attrs) and (batch, attrs, boxes) formats
    if prediction.ndim == 3:
        # YOLO outputs (batch, attrs, boxes) — transpose to (batch, boxes, attrs)
        if prediction.shape[1] < prediction.shape[2]:
            prediction = np.transpose(prediction, (0, 2, 1))

    for batch_pred in prediction:
        # batch_pred shape: (num_boxes, 4 + num_classes) or (num_boxes, 4 + 1 + num_classes)
        num_attrs = batch_pred.shape[1]

        if num_attrs > 5:
            # Format: x_center, y_center, w, h, class_scores...
            # No explicit objectness — YOLOv8+ format
            boxes_xywh = batch_pred[:, :4]
            class_scores = batch_pred[:, 4:]
            cls_ids = np.argmax(class_scores, axis=1)
            confs = class_scores[np.arange(len(class_scores)), cls_ids]
        elif num_attrs == 5:
            # Format: x_center, y_center, w, h, conf (single class)
            boxes_xywh = batch_pred[:, :4]
            confs = batch_pred[:, 4]
            cls_ids = np.zeros(len(batch_pred), dtype=int)
        else:
            output.append(np.zeros((0, 6), dtype=np.float32))
            continue

        # Filter by confidence
        mask = confs > conf_thres
        if not np.any(mask):
            output.append(np.zeros((0, 6), dtype=np.float32))
            continue

        boxes_xywh = boxes_xywh[mask]
        confs = confs[mask]
        cls_ids = cls_ids[mask]

        # Convert xywh to xyxy
        x1 = boxes_xywh[:, 0] - boxes_xywh[:, 2] / 2
        y1 = boxes_xywh[:, 1] - boxes_xywh[:, 3] / 2
        x2 = boxes_xywh[:, 0] + boxes_xywh[:, 2] / 2
        y2 = boxes_xywh[:, 1] + boxes_xywh[:, 3] / 2
        boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

        # NMS per class
        unique_classes = np.unique(cls_ids)
        final_boxes = []
        final_confs = []
        final_cls = []

        for c in unique_classes:
            c_mask = cls_ids == c
            c_boxes = boxes_xyxy[c_mask]
            c_confs = confs[c_mask]
            keep = numpy_nms(c_boxes, c_confs, iou_thres)
            final_boxes.append(c_boxes[keep])
            final_confs.append(c_confs[keep])
            final_cls.append(np.full(len(keep), c, dtype=np.float32))

        if final_boxes:
            final_boxes = np.concatenate(final_boxes)
            final_confs = np.concatenate(final_confs)
            final_cls = np.concatenate(final_cls)
            result = np.column_stack([final_boxes, final_confs, final_cls])
        else:
            result = np.zeros((0, 6), dtype=np.float32)

        output.append(result)

    return output


class Detect:
    def __init__(self, model_path, ignore_classes=None, classes=None, input_size=(640, 640)):
        self.preferred_device = load_toml_as_dict("cfg/general_config.toml")['cpu_or_gpu']
        self.model_path = model_path
        self.classes = classes
        self.ignore_classes = ignore_classes if ignore_classes else []
        self.input_size = input_size
        self.model, self.device = self.load_model()
        self._input_name = self.model.get_inputs()[0].name

        self._warmup()

    def load_model(self):
        available_providers = ort.get_available_providers()
        onnx_provider = "CPUExecutionProvider"

        if self.preferred_device in ("gpu", "auto"):
            if "DmlExecutionProvider" in available_providers:
                onnx_provider = "DmlExecutionProvider"
                print(f"Loaded DirectML provider for: {self.model_path}")
            elif "CUDAExecutionProvider" in available_providers:
                onnx_provider = "CUDAExecutionProvider"
                print(f"Loaded CUDA provider for: {self.model_path}")
            elif "AzureExecutionProvider" in available_providers:
                onnx_provider = "AzureExecutionProvider"
                print(f"[GPU] Using Azure provider for: {self.model_path}")
            else:
                print(f"No GPU provider found (using CPU) for: {self.model_path}")
        else:
            print(f"CPU mode selected for: {self.model_path}")

        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        so.intra_op_num_threads = 0

        model = ort.InferenceSession(self.model_path, sess_options=so, providers=[onnx_provider])
        return model, onnx_provider

    def _warmup(self):
        """Run dummy inferences to warm up the model."""
        dummy = np.random.rand(1, 3, *self.input_size).astype(np.float32)
        for _ in range(2):
            self.model.run(None, {self._input_name: dummy})

    def preprocess_image(self, img):
        if isinstance(img, Image.Image):
            img = np.array(img)

        h, w, _ = img.shape
        scale = min(self.input_size[0] / h, self.input_size[1] / w)
        new_w = int(w * scale)
        new_h = int(h * scale)

        resized_img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        padded_img = np.full((self.input_size[0], self.input_size[1], 3), 128, dtype=np.uint8)
        padded_img[:new_h, :new_w, :] = resized_img

        padded_img = padded_img.astype(np.float32) / 255.0
        padded_img = np.transpose(padded_img, (2, 0, 1))
        padded_img = np.expand_dims(padded_img, axis=0)

        return padded_img, new_w, new_h

    def postprocess(self, preds, orig_img_shape, resized_shape, conf_tresh=0.6):
        preds = numpy_non_max_suppression(preds, conf_thres=conf_tresh, iou_thres=0.6)

        orig_h, orig_w = orig_img_shape
        resized_w, resized_h = resized_shape
        scale_w = orig_w / resized_w
        scale_h = orig_h / resized_h

        results = []
        for pred in preds:
            if len(pred):
                pred[:, 0] *= scale_w
                pred[:, 1] *= scale_h
                pred[:, 2] *= scale_w
                pred[:, 3] *= scale_h
                results.append(pred)

        return results

    def detect_objects(self, img, conf_tresh=0.6):
        if isinstance(img, Image.Image):
            img = np.array(img)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        orig_h, orig_w = img.shape[:2]
        preprocessed_img, resized_w, resized_h = self.preprocess_image(img)

        outputs = self.model.run(None, {self._input_name: preprocessed_img})

        detections = self.postprocess(outputs[0], (orig_h, orig_w), (resized_w, resized_h), conf_tresh)

        results = {}
        for detection in detections:
            for *xyxy, conf, cls in detection:
                x1, y1, x2, y2 = map(int, xyxy)
                class_id = int(cls)
                class_name = self.classes[class_id]

                if class_id in self.ignore_classes or class_name in self.ignore_classes:
                    continue
                if class_name not in results:
                    results[class_name] = []
                results[class_name].append([x1, y1, x2, y2])

        return results
