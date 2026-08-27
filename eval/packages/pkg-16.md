# Eval package: pkg-16

- source: kubernetes/minikube#23471
- captured: 2026-08-18
- calibration: false

## Repo facts (captured 2026-08-18)

- repo: kubernetes/minikube (32045 stars, archived: no)
- description: Run Kubernetes locally.
- latest release: v1.38.1 (2026-02-19)
- pull requests: template hints ask for a release-notes-quality PR title, a "fixes #<issue number>" line in the description, and before/after examples for user-interface changes
- contribution policy (CONTRIBUTING.md): Kubernetes contribution process (CLA, community guidelines); no stated AI policy

## Issue

### `minikube image load` exits 0 and prints nothing when the guest-side load fails (#23471)

opened by ravi-arnan (NONE) on 2026-08-10, state open, labels: none

`minikube image load` returns exit code 0 when the image was not
loaded; in the clearest case it also prints nothing, so both a human
and a CI script see an unqualified success for a no-op.

```console
$ printf 'this is not a tar archive at all\n' > notanimage.tar
$ minikube image load ./notanimage.tar -p exitcode
$ echo $?
0
$ minikube -p exitcode ssh -- docker images | grep notanimage
$                      # nothing was loaded
```

The failure is only visible with `-v=3`. Why: `DoLoadImages`
(`pkg/minikube/machine/cache_images.go`) accumulates per-machine
failures into `failed`, logs them through klog (invisible at default
verbosity), and returns `nil` unconditionally ("Live pushes are not
considered a failure"). A corrupt or truncated tarball is the
realistic version: clean exit, absent image, nothing pointing at
what went wrong.

## Thread highlights (3 comments total)

- 2026-08-16 nirs (MEMBER): thanks, points at a related PR for review.
- 2026-08-16 nirs (MEMBER): on the reporter's caution about `DoLoadImages` being shared with the start-time loading path: "minikube start starts only one profile - maybe you mean multiple node?"
- 2026-08-17 ravi-arnan (NONE): confirms: the multi-item case on the start path is multi-node, not multi-profile; `cmd/image.go` passes one profile.

## Plan context

The accepted plan this PR claims to implement, excerpted from the
posted plan (with the repro evidence it built on):

Repro evidence (from the accepted report): the issue's not-a-tar
repro re-run on v1.38.1: exit 0, empty output, no image in the
guest; `-v=3` shows the swallowed
`Failed to load cached images ... Process exited with status 1`,
confirming the error exists and is discarded in `DoLoadImages`.

Plan: make the failure visible on the `image load` path without
changing the start path's semantics. Scope, one bounded change:
`DoLoadImages` returns an aggregated error when every target machine
failed; `cmd/image.go`'s load command surfaces that error to the
user and exits non-zero. Deliberately deferred, stated in the plan:
the start-time loading path (multi-node, where a per-node failure
may genuinely be non-fatal) keeps its current tolerant behavior;
which start-path failures should become fatal is a maintainer
decision the plan leaves open, per the thread. Files:
`pkg/minikube/machine/cache_images.go`, `cmd/minikube/cmd/image.go`,
unit test for the aggregation. Test plan: re-run the not-a-tar
repro, expect a printed error naming the image and exit 1; a valid
tarball control still loads with exit 0; `go test` on the touched
packages.

## Candidate PR

### Title

image load: fail loudly when the guest-side load fails

### Description

fixes #23471

`minikube image load` swallowed guest-side failures: `DoLoadImages`
logged them at klog verbosity and returned nil, so a corrupt tarball
produced exit 0 and silence. Per the plan on the issue,
`DoLoadImages` now returns an aggregated error when all target
machines failed, and the `image load` command surfaces it and exits
non-zero.

Before:

```
$ minikube image load ./notanimage.tar && echo OK
OK
```

After:

```
$ minikube image load ./notanimage.tar && echo OK
X Failed to load image ./notanimage.tar: docker load: invalid tar header
$ echo $?
1
```

Deliberately out of scope (recorded in the plan and discussed with
@nirs on the thread): the start-time image loading path keeps its
tolerant behavior; a per-node failure at start is not necessarily
fatal, and changing that is a separate decision.

### Commits

- 74d8f0e machine: return aggregated error from DoLoadImages when all targets fail
- ab112c9 cmd: surface image load failures and exit non-zero

### Diff

```diff
--- a/pkg/minikube/machine/cache_images.go
+++ b/pkg/minikube/machine/cache_images.go
@@ -246,15 +246,23 @@ func DoLoadImages(images []string, profiles []*config.Profile, cacheDir string,
+	var loadErrs []error
 	for _, m := range machines {
 		if err != nil {
 			failed = append(failed, m)
 			klog.Warningf("Failed to load cached images for %q: %v", pName, err)
+			loadErrs = append(loadErrs, fmt.Errorf("%s: %w", pName, err))
 			continue
 		}
 		succeeded = append(succeeded, m)
 	}
 	if len(failed) > 0 {
 		klog.Infof("failed pushing to: %s", strings.Join(failed, " "))
+		// Image-load callers need the failure: when nothing succeeded,
+		// the operation failed, whatever the start path tolerates
+		// (#23471).
+		if len(succeeded) == 0 {
+			return fmt.Errorf("loading images: %w", errors.Join(loadErrs...))
+		}
 	}
-	// Live pushes are not considered a failure
+	// Partial success stays non-fatal for the multi-node start path.
 	return nil
--- a/cmd/minikube/cmd/image.go
+++ b/cmd/minikube/cmd/image.go
@@ -139,7 +139,9 @@ var loadImageCmd = &cobra.Command{
-		if err := machine.DoLoadImages(images, []*config.Profile{profile}, "", false); err != nil {
-			klog.Warningf("load failed: %v", err)
-		}
+		if err := machine.DoLoadImages(images, []*config.Profile{profile}, "", false); err != nil {
+			exit.Error(reason.GuestImageLoad, "Failed to load image", err)
+		}
--- a/pkg/minikube/machine/cache_images_test.go
+++ b/pkg/minikube/machine/cache_images_test.go
@@ -88,3 +88,14 @@ func TestDoLoadImagesSuccess(t *testing.T) {
+
+func TestDoLoadImagesAllFailedReturnsError(t *testing.T) {
+	// #23471: a total failure must not return nil.
+	err := doLoadImagesWith(t, allTargetsFail)
+	if err == nil {
+		t.Fatal("expected aggregated error, got nil")
+	}
+	if !strings.Contains(err.Error(), "loading images") {
+		t.Fatalf("unexpected error: %v", err)
+	}
+}
```

### Test evidence

Repro re-run on the branch (before/after in the description, full
transcript):

```
$ minikube image load ./notanimage.tar -p exitcode
X Failed to load image ./notanimage.tar: docker load: invalid tar header
$ echo $?
1
$ minikube image load ./alpine.tar -p exitcode && echo $?
0
$ minikube -p exitcode ssh -- docker images | grep alpine
alpine    latest    b0c9d60fc5e3   ...
```

Expected-after per the plan: loud error and exit 1 on the corrupt
tarball; valid-tarball control unchanged. `go test
./pkg/minikube/machine/... ./cmd/...` passes.
