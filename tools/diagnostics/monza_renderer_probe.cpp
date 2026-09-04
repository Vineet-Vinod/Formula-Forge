// Standalone diagnostic. Links the game's raylib/SDL libraries; no game
// changes. Arguments: asset vs fs output near eyeX eyeY eyeZ targetX targetY
// targetZ [reverse]
#include <SDL3/SDL.h>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <raylib.h>
#include <raymath.h>
#include <rlgl.h>
#include <vector>

int main(int argc, char **argv) {
  if (argc < 12)
    return 2;
  SetConfigFlags(FLAG_WINDOW_HIDDEN | FLAG_MSAA_4X_HINT);
  if (const char *bits = std::getenv("FORENSICS_DEPTH_BITS")) {
    SDL_Init(SDL_INIT_VIDEO);
    SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, atoi(bits));
  }
  InitWindow(1280, 720, "Monza renderer forensic probe");
  int depth = 0, samples = 0;
  SDL_GL_GetAttribute(SDL_GL_MULTISAMPLESAMPLES, &samples);
  SDL_GL_GetAttribute(SDL_GL_DEPTH_SIZE, &depth);
  using GetString = const unsigned char *(*)(unsigned);
  auto getString =
      reinterpret_cast<GetString>(SDL_GL_GetProcAddress("glGetString"));
  printf("FORENSICS depth_bits=%d samples=%d near=%s far=4000 renderer=%s "
         "version=%s\n",
         depth, samples, argv[5], getString(0x1F01), getString(0x1F02));
  Model model = LoadModel(argv[1]);
  Shader shader = LoadShader(argv[2], argv[3]);
  shader.locs[SHADER_LOC_MATRIX_MODEL] = GetShaderLocation(shader, "matModel");
  shader.locs[SHADER_LOC_MATRIX_NORMAL] =
      GetShaderLocation(shader, "matNormal");
  auto scalar = [&](const char *n, float x) {
    SetShaderValue(shader, GetShaderLocation(shader, n), &x,
                   SHADER_UNIFORM_FLOAT);
  };
  auto vector = [&](const char *n, Vector3 x) {
    SetShaderValue(shader, GetShaderLocation(shader, n), &x,
                   SHADER_UNIFORM_VEC3);
  };
  Camera3D camera{
      {float(atof(argv[6])), float(atof(argv[7])), float(atof(argv[8]))},
      {float(atof(argv[9])), float(atof(argv[10])), float(atof(argv[11]))},
      {0, 1, 0},
      60,
      CAMERA_PERSPECTIVE};
  vector("viewPos", camera.position);
  vector("sunDirection", Vector3Normalize({-.42f, .78f, -.46f}));
  vector("sunColor", {1, 238 / 255.f, 196 / 255.f});
  vector("skyAmbient",
         {117 / 255.f * .56f, 177 / 255.f * .56f, 205 / 255.f * .56f});
  vector("groundAmbient",
         {85 / 255.f * .34f, 93 / 255.f * .34f, 74 / 255.f * .34f});
  vector("fogColor", {146 / 255.f, 213 / 255.f, 226 / 255.f});
  scalar("fogStart", 10000);
  scalar("fogEnd", 12000);
  scalar("exposure", 1);
  scalar("materialGloss", .08f);
  scalar("alphaCutoff", .35f);
  std::vector<BoundingBox> boxes;
  for (int i = 0; i < model.meshCount; ++i)
    boxes.push_back(GetMeshBoundingBox(model.meshes[i]));
  for (int i = 0; i < model.materialCount; ++i) {
    auto &t = model.materials[i].maps[MATERIAL_MAP_DIFFUSE].texture;
    if (t.id) {
      GenTextureMipmaps(&t);
      SetTextureFilter(t, TEXTURE_FILTER_ANISOTROPIC_8X);
    }
  }
  rlSetClipPlanes(atof(argv[5]), 4000);
  for (int frame = 0; frame < 3; ++frame) {
    BeginDrawing();
    ClearBackground({76, 184, 224, 255});
    BeginMode3D(camera);
    rlDisableBackfaceCulling();
    auto vp = MatrixMultiply(rlGetMatrixModelview(), rlGetMatrixProjection());
    std::vector<std::pair<float, int>> order;
    for (int i = 0; i < model.meshCount; ++i) {
      auto b = boxes[i];
      unsigned outside = 63;
      for (int k = 0; k < 8; ++k) {
        float x = ((k & 1) ? b.max.x : b.min.x) * 1.445f,
              y = ((k & 2) ? b.max.y : b.min.y) * 1.445f,
              z = ((k & 4) ? b.max.z : b.min.z) * 1.445f;
        float cx = vp.m0 * x + vp.m4 * y + vp.m8 * z + vp.m12,
              cy = vp.m1 * x + vp.m5 * y + vp.m9 * z + vp.m13,
              cz = vp.m2 * x + vp.m6 * y + vp.m10 * z + vp.m14,
              cw = vp.m3 * x + vp.m7 * y + vp.m11 * z + vp.m15;
        outside &= (cx < -cw ? 1u : 0u) | (cx > cw ? 2u : 0u) |
                   (cy < -cw ? 4u : 0u) | (cy > cw ? 8u : 0u) |
                   (cz < -cw ? 16u : 0u) | (cz > cw ? 32u : 0u);
      }
      if (outside)
        continue;
      auto c = Vector3Scale(Vector3Add(b.min, b.max), 1.445f * .5f);
      order.emplace_back(vp.m3 * c.x + vp.m7 * c.y + vp.m11 * c.z + vp.m15, i);
    }
    std::sort(order.begin(), order.end());
    if (argc > 12 && atoi(argv[12]))
      std::reverse(order.begin(), order.end());
    for (auto [d, i] : order) {
      auto mat = model.materials[model.meshMaterial[i]];
      mat.shader = shader;
      DrawMesh(model.meshes[i], mat, MatrixScale(1.445f, 1.445f, 1.445f));
    }
    EndMode3D();
    if (frame == 2) {
      rlDrawRenderBatchActive();
      Image shot = LoadImageFromScreen();
      ExportImage(shot, argv[4]);
      UnloadImage(shot);
    }
    EndDrawing();
  }
  printf("FORENSICS meshes=%d materials=%d shader=%u\n", model.meshCount,
         model.materialCount, shader.id);
  UnloadModel(model);
  UnloadShader(shader);
  CloseWindow();
}
