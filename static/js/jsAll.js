// Đặt hàm này vào file JS chung hoặc trong <script> ở base.html

/**
 * Hiển thị một thông báo Bootstrap Toast động.
 * @param {string} message Nội dung thông báo.
 * @param {string} category Loại thông báo ('success', 'danger', 'warning', 'info', 'primary', 'secondary', 'light', 'dark') - để xác định màu nền. Mặc định là 'info'.
 * @param {number} delay Thời gian tự động ẩn (miliseconds). Mặc định 5000 (5 giây).
 */
function showBootstrapToast(message, category = 'info', delay = 7000) {
    const toastContainer = document.querySelector('.toast-container'); // Tìm container đã có trong base.html

    // Nếu không tìm thấy container -> dùng alert dự phòng
    if (!toastContainer) {
        console.error('Toast container (.toast-container) not found in base.html!');
        alert(message); // Fallback
        return;
    }

    const toastId = 'dynamic-toast-' + Date.now(); // Tạo ID duy nhất cho mỗi toast
    const bgClass = `text-bg-${category}`; // Class màu nền của Bootstrap

    // Tạo HTML cho Toast
    const toastHTML = `
    <div id="${toastId}" class="toast align-items-center ${bgClass} border-0" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="d-flex">
        <div class="toast-body">
          ${message}  
        </div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
    </div>`;

    // Thêm Toast HTML vào container
    toastContainer.insertAdjacentHTML('beforeend', toastHTML);

    // Lấy element toast vừa thêm
    const toastElement = document.getElementById(toastId);

    if (toastElement) {
        // Khởi tạo đối tượng Toast của Bootstrap
        const toast = new bootstrap.Toast(toastElement, {
            delay: delay // Đặt thời gian tự ẩn
        });
        toast.show(); // Hiển thị toast

        // (Tùy chọn) Tự động xóa element khỏi DOM sau khi toast đã ẩn hoàn toàn
        toastElement.addEventListener('hidden.bs.toast', function () {
            toastElement.remove();
        });
    }
}