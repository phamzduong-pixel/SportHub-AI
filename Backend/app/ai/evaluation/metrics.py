from sklearn.metrics import accuracy_score, confusion_matrix, precision_score, recall_score, f1_score

LABELS = ['LOW', 'MEDIUM', 'HIGH']


def calculate_metrics(y_true, y_pred) -> dict:
    return {
        'accuracy': round(float(accuracy_score(y_true, y_pred)), 4),
        'precision': round(float(precision_score(y_true, y_pred, labels=LABELS, average='weighted', zero_division=0)), 4),
        'recall': round(float(recall_score(y_true, y_pred, labels=LABELS, average='weighted', zero_division=0)), 4),
        'f1_score': round(float(f1_score(y_true, y_pred, labels=LABELS, average='weighted', zero_division=0)), 4),
        'confusion_matrix': confusion_matrix(y_true, y_pred, labels=LABELS).tolist(),
        'labels': LABELS,
    }
