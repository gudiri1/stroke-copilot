.PHONY: proto demo clean check

proto:            ## regenerate proto/messages.py from model/model.yaml
	python3 tools/gen_proto.py model/model.yaml proto/messages.py

check: proto      ## fail if the committed proto is stale
	git diff --exit-code proto/messages.py

demo:             ## run the full chain on synthetic frames
	python3 tools/run_demo.py

clean:
	rm -rf out/* __pycache__ src/__pycache__ proto/__pycache__
