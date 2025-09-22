let taskId = null;

async function uploadFile() {
  const fileInput = document.getElementById("fileInput");
  if (fileInput.files.length === 0) return;

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  const response = await fetch("http://localhost:8000/upload/", {
    method: "POST",
    body: formData
  });
  const data = await response.json();
  taskId = data.task_id;

  checkProgress();
}

async function checkProgress() {
  if (!taskId) return;

  const response = await fetch(`http://localhost:8000/progress/${taskId}`);
  const data = await response.json();

  document.getElementById("progressBar").value = data.progress;
  document.getElementById("status").innerText = `Прогресс: ${data.progress}%`;

  if (data.progress < 100) {
    setTimeout(checkProgress, 2000);
  } else {
    document.getElementById("status").innerText = "Готово! Можно скачать результат.";
  }
}
