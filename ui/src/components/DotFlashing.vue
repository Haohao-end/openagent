<script setup lang="ts"></script>

<template>
  <div class="h-5 w-5 flex items-center justify-center">
    <div class="dot-flashing text"></div>
  </div>
</template>

<style scoped>
.dot-flashing {
  position: relative;
  animation: 1s infinite linear alternate;
  animation-delay: 0.5s;
}

.dot-flashing::before,
.dot-flashing::after {
  content: '';
  display: inline-block;
  position: absolute;
  top: 0;
  animation: 1s infinite linear alternate;
}

.dot-flashing::before {
  animation-delay: 0s;
}

.dot-flashing::after {
  animation-delay: 1s;
}

@keyframes dot-flashing {
  0% {
    background-color: #667085;
  }

  50%,
  100% {
    background-color: rgba(102, 112, 133, 0.3);
  }
}

@keyframes dot-flashing-avatar {
  0% {
    background-color: #155eef;
  }

  50%,
  100% {
    background-color: rgba(21, 94, 239, 0.3);
  }
}

.text,
.text::before,
.text::after {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background-color: #667085;
  color: #667085;
  animation-name: dot-flashing;
}

.text::before {
  left: -7px;
}

.text::after {
  left: 7px;
}
</style>
